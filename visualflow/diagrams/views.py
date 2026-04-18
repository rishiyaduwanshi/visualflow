"""
Views for the VisualFlow diagram generation application
"""

import logging
import json
from datetime import timedelta
from django.shortcuts import redirect, render, get_object_or_404
from django.views.generic import TemplateView, ListView, DetailView
from django.views import View
from django.http import HttpResponse, JsonResponse
from django.contrib import messages
from django.db.models import Q
from django.utils import timezone
from django.contrib.auth import login
from django.contrib.auth.forms import UserCreationForm
from django.contrib.auth.views import LoginView, LogoutView
from django.urls import reverse_lazy

from .models import Session, Contact, AppSettings
from .forms import ContactForm
from config.constants import AppConstants

logger = logging.getLogger(__name__)


def _can_view_session(request, session: Session) -> bool:
    if session.is_public:
        return True
    return request.user.is_authenticated and session.owner_id == request.user.id


def _can_manage_session(request, session: Session) -> bool:
    return request.user.is_authenticated and session.owner_id == request.user.id


class SignUpView(View):
    template_name = 'registration/signup.html'

    def get(self, request):
        if request.user.is_authenticated:
            return redirect('diagrams:home')
        return render(request, self.template_name, {'form': UserCreationForm()})

    def post(self, request):
        if request.user.is_authenticated:
            return redirect('diagrams:home')

        form = UserCreationForm(request.POST)
        if form.is_valid():
            user = form.save()
            login(request, user)
            messages.success(request, 'Account created successfully.')
            return redirect('diagrams:home')

        return render(request, self.template_name, {'form': form})


class UserLoginView(LoginView):
    template_name = 'registration/login.html'
    redirect_authenticated_user = True


class UserLogoutView(LogoutView):
    next_page = reverse_lazy('diagrams:home')

def handleContactForm(request):
    if request.method == 'POST':
        form = ContactForm(request.POST)
        if form.is_valid():
            form.save()
            messages.success(request, 'Your message has been sent successfully!')
            return redirect('diagrams:contact')
    else:
        form = ContactForm()
    
    return render(request, 'diagrams/contact.html', {'form': form})

def delete_diagram(request, diagram_id):
    if request.method == 'POST':
        diagram = get_object_or_404(Session, id=diagram_id)
        if not _can_manage_session(request, diagram):
            messages.error(request, 'You do not have permission to delete this diagram.')
            return redirect('diagrams:history')
        diagram.delete()
        messages.success(request, 'Diagram deleted successfully!')
        return redirect('diagrams:history')
    return redirect('diagrams:history')

class HomeView(TemplateView):
    """
    Homepage view with diagram generation form
    """
    template_name = 'diagrams/home.html'
    
    def get_context_data(self, **kwargs):
        """Add additional context to the template"""
        context = super().get_context_data(**kwargs)
        if self.request.user.is_authenticated:
            recent_sessions = Session.objects.filter(
                status='completed'
            ).filter(
                Q(owner=self.request.user) | Q(is_public=True)
            )[:5]
        else:
            recent_sessions = Session.objects.filter(status='completed', is_public=True)[:5]

        context.update({
            'diagram_types': AppConstants.DIAGRAM_TYPES,
            'default_prompts': AppConstants.DEFAULT_PROMPTS,
            'app_name': 'VisualFlow',
            'recent_sessions': recent_sessions,
        })
        return context


class GenerateDiagramView(View):
    """
    Handle diagram generation requests
    """
    
    def post(self, request):
        """
        Process diagram generation form submission
        """
        try:
            if not request.user.is_authenticated:
                messages.error(request, 'Please login to generate diagrams.')
                return redirect('diagrams:login')

            # Get form data
            prompt = request.POST.get('prompt', '').strip()
            diagram_type = request.POST.get('diagram_type', '').strip()
            is_public = request.POST.get('is_public') == 'on'
            
            # Validate input
            if not prompt:
                messages.error(request, AppConstants.MESSAGES['ERROR']['INVALID_PROMPT'])
                return redirect('diagrams:home')
            
            if len(prompt) < 10:
                messages.error(request, "Prompt must be at least 10 characters long.")
                return redirect('diagrams:home')
            
            # Auto-detect diagram type if not provided (simple detection)
            if not diagram_type or diagram_type == 'auto':
                diagram_type = self._simple_detect_diagram_type(prompt)
                logger.info(f"Auto-detected diagram type: {diagram_type}")
            
            # Validate diagram type
            if diagram_type not in AppConstants.DIAGRAM_TYPES.values():
                diagram_type = 'custom'
            
            # ========================================
            # 🛡️ DUPLICATE REQUEST PROTECTION
            # ========================================
            # Check for recent pending/processing sessions to prevent:
            # - Accidental double-clicks
            # - Multiple concurrent API calls
            # - Database pollution
            # - Rate limit exhaustion
            
            user_ip = self._get_client_ip(request)
            
            # Check for identical requests within last 30 seconds
            recent_cutoff = timezone.now() - timedelta(seconds=30)
            duplicate_session = Session.objects.filter(
                owner=request.user,
                user_ip=user_ip,
                prompt=prompt,
                created_at__gte=recent_cutoff,
                status__in=['processing', 'completed']
            ).order_by('-created_at').first()
            
            if duplicate_session:
                logger.warning(f"🚫 Duplicate request detected from IP {user_ip}. Returning existing session {duplicate_session.id}")
                messages.info(request, "⚡ Using your recent request to avoid duplication.")
                return redirect('diagrams:display', session_id=duplicate_session.id)
            
            # Check for too many requests from same IP (rate limiting)
            recent_requests = Session.objects.filter(
                owner=request.user,
                user_ip=user_ip,
                created_at__gte=recent_cutoff
            ).count()
            
            if recent_requests >= 3:  # Max 3 requests per 30 seconds
                logger.warning(f"🚫 Rate limit exceeded for IP {user_ip}")
                messages.error(request, "⏳ Too many requests! Please wait 30 seconds before generating another diagram.")
                return redirect('diagrams:home')
            
            # Create session
            session = Session.objects.create(
                prompt=prompt,
                diagram_type=diagram_type,
                owner=request.user,
                is_public=is_public,
                status='processing',
                user_ip=user_ip,
                user_agent=request.META.get('HTTP_USER_AGENT', '')
            )
            
            # Generate diagram asynchronously (for now, synchronously)
            self._generate_diagram_sync(session)
            
            # Redirect to display page
            if session.status == 'completed':
                messages.success(request, AppConstants.MESSAGES['SUCCESS']['DIAGRAM_GENERATED'])
                return redirect('diagrams:display', session_id=session.id)
            else:
                messages.error(request, AppConstants.MESSAGES['ERROR']['GENERATION_FAILED'])
                return redirect('diagrams:home')
                
        except Exception as e:
            logger.error(f"Error in diagram generation: {str(e)}")
            messages.error(request, AppConstants.MESSAGES['ERROR']['GENERATION_FAILED'])
            return redirect('diagrams:home')
    
    def _simple_detect_diagram_type(self, prompt: str) -> str:
        """Simple diagram type detection based on keywords"""
        prompt_lower = prompt.lower()
        
        if any(word in prompt_lower for word in ['flow', 'process', 'workflow', 'step']):
            return 'flowchart'
        elif any(word in prompt_lower for word in ['sequence', 'interaction', 'timeline']):
            return 'sequence'
        elif any(word in prompt_lower for word in ['class', 'uml', 'object']):
            return 'class'
        elif any(word in prompt_lower for word in ['database', 'entity', 'relationship', 'table', 'erd']):
            return 'er'
        elif any(word in prompt_lower for word in ['state', 'transition', 'status']):
            return 'state'
        else:
            return 'flowchart'
    
    def _get_client_ip(self, request):
        """Get client IP address"""
        x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
        if x_forwarded_for:
            ip = x_forwarded_for.split(',')[0]
        else:
            ip = request.META.get('REMOTE_ADDR')
        return ip
    
    def _generate_diagram_sync(self, session):
        """
        Generate Mermaid diagram synchronously - Simple and reliable
        """
        try:
            # Use simple Mermaid service
            from .services.mermaid_service import mermaid_service
            
            # Generate Mermaid code based on diagram type
            mermaid_code, error, detected_type = mermaid_service.generate_mermaid_code(
                session.prompt, 
                session.diagram_type
            )
            
            if not mermaid_code:
                session.status = 'failed'
                session.error_message = error or "Failed to generate Mermaid code"
                session.save()
                return

            if error:
                logger.warning(f"Generation warning for session {session.id}: {error}")
            
            # Update diagram type if AI detected a better one
            if detected_type and detected_type != session.diagram_type:
                logger.info(f"AI detected diagram type: {detected_type} (original: {session.diagram_type})")
                session.diagram_type = detected_type
            
            # Save results - Mermaid renders in frontend, no server-side SVG needed
            session.generated_uml = mermaid_code
            session.diagram_svg = mermaid_code  # Store Mermaid code for frontend rendering
            session.status = 'completed'
            session.save()
            
            logger.info(f"Successfully generated Mermaid diagram for session {session.id}")
            
        except Exception as e:
            session.status = 'failed'
            session.error_message = str(e)
            session.save()
            logger.error(f"Error generating diagram for session {session.id}: {str(e)}")


class RepairDiagramView(View):
    """
    Repair Mermaid diagram from frontend runtime render errors.
    """

    def post(self, request, session_id):
        try:
            session = Session.objects.get(id=session_id)
            if not _can_manage_session(request, session):
                return JsonResponse({'success': False, 'error': 'Permission denied'}, status=403)

            payload = json.loads(request.body.decode('utf-8')) if request.body else {}

            render_error = (payload.get('render_error') or '').strip()
            failed_code = (payload.get('failed_code') or '').strip()
            attempt = int(payload.get('attempt') or 1)

            if not render_error:
                return JsonResponse({'success': False, 'error': 'Missing render error details'}, status=400)

            from .services.mermaid_service import mermaid_service

            repaired_code, repair_error = mermaid_service.regenerate_from_render_error(
                prompt=session.prompt,
                diagram_type=session.diagram_type,
                current_code=failed_code or session.generated_uml or '',
                render_error=render_error,
                attempt=attempt,
            )

            if not repaired_code:
                return JsonResponse({'success': False, 'error': repair_error or 'Failed to repair diagram'}, status=422)

            session.generated_uml = repaired_code
            session.diagram_svg = repaired_code
            session.error_message = None
            session.status = 'completed'
            session.save()

            return JsonResponse({
                'success': True,
                'mermaid_code': repaired_code,
                'warning': repair_error,
            })

        except Session.DoesNotExist:
            return JsonResponse({'success': False, 'error': 'Session not found'}, status=404)
        except (ValueError, TypeError):
            return JsonResponse({'success': False, 'error': 'Invalid payload'}, status=400)
        except Exception as e:
            logger.error(f"Error repairing diagram for session {session_id}: {str(e)}")
            return JsonResponse({'success': False, 'error': 'Internal server error'}, status=500)


class DiagramDisplayView(DetailView):
    """
    Display generated diagram
    """
    model = Session
    template_name = 'diagrams/display.html'
    context_object_name = 'session'
    pk_url_kwarg = 'session_id'

    def get_queryset(self):
        queryset = super().get_queryset()
        if self.request.user.is_authenticated:
            return queryset.filter(Q(is_public=True) | Q(owner=self.request.user))
        return queryset.filter(is_public=True)
    
    def get_context_data(self, **kwargs):
        """Add additional context"""
        context = super().get_context_data(**kwargs)
        session = self.get_object()

        processing_timeout = timezone.now() - timedelta(minutes=2)
        if session.status == 'processing' and session.created_at <= processing_timeout:
            session.status = 'failed'
            session.error_message = 'Generation timed out. Please try again.'
            session.save(update_fields=['status', 'error_message', 'updated_at'])

        app_settings = AppSettings.load()

        context.update({
            'diagram_type_display': AppConstants.DIAGRAM_TYPE_DISPLAY.get(
                session.diagram_type, session.diagram_type.upper()
            ),
            'debug_mode': app_settings.mermaid_debug_mode,
            'can_repair': _can_manage_session(self.request, session),
        })
        return context


class SessionHistoryView(ListView):
    """
    Display session history
    """
    model = Session
    template_name = 'diagrams/history.html'
    context_object_name = 'sessions'
    paginate_by = AppConstants.ITEMS_PER_PAGE
    ordering = ['-created_at']
    
    def get_queryset(self):
        """Filter and order sessions"""
        queryset = super().get_queryset()

        if self.request.user.is_authenticated:
            queryset = queryset.filter(Q(is_public=True) | Q(owner=self.request.user))
        else:
            queryset = queryset.filter(is_public=True)

        visibility = self.request.GET.get('visibility')
        if visibility == 'public':
            queryset = queryset.filter(is_public=True)
        elif visibility == 'private' and self.request.user.is_authenticated:
            queryset = queryset.filter(is_public=False, owner=self.request.user)
        
        # Filter by diagram type if specified
        diagram_type = self.request.GET.get('type')
        if diagram_type and diagram_type in AppConstants.DIAGRAM_TYPES.values():
            queryset = queryset.filter(diagram_type=diagram_type)
        
        # Filter by status
        status = self.request.GET.get('status')
        if status in ['completed', 'failed', 'processing']:
            queryset = queryset.filter(status=status)
        
        return queryset
    
    def get_context_data(self, **kwargs):
        """Add filter context"""
        context = super().get_context_data(**kwargs)
        context.update({
            'diagram_types': AppConstants.DIAGRAM_TYPES,
            'current_type': self.request.GET.get('type', ''),
            'current_status': self.request.GET.get('status', ''),
            'current_visibility': self.request.GET.get('visibility', ''),
        })
        return context


class DownloadView(View):
    """Download diagram as image or code"""
    
    def get(self, request, session_id):
        try:
            session = Session.objects.get(id=session_id)
            if not _can_view_session(request, session):
                return HttpResponse("Diagram not found", status=404)

            format_type = request.GET.get('format', 'png')
            
            if format_type == 'mmd':
                # Download Mermaid code
                response = HttpResponse(session.generated_uml, content_type='text/plain')
                response['Content-Disposition'] = f'attachment; filename="diagram_{session.id}.mmd"'
                return response
            else:
                # For image download, return HTML page with conversion script
                context = {
                    'session': session,
                    'mermaid_code': session.generated_uml,
                    'format_type': format_type
                }
                return render(request, 'diagrams/download.html', context)
                
        except Session.DoesNotExist:
            return HttpResponse("Diagram not found", status=404)

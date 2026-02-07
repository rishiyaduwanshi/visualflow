"""
Views for the VisualFlow diagram generation application
"""

import logging
from django.shortcuts import redirect, render, get_object_or_404
from django.views.generic import TemplateView, ListView, DetailView
from django.views import View
from django.http import HttpResponse
from django.contrib import messages

from .models import Session, Contact
from .forms import ContactForm
from config.constants import AppConstants

logger = logging.getLogger(__name__)

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
        context.update({
            'diagram_types': AppConstants.DIAGRAM_TYPES,
            'default_prompts': AppConstants.DEFAULT_PROMPTS,
            'app_name': 'VisualFlow',
            'recent_sessions': Session.objects.filter(status='completed')[:5]
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
            # Get form data
            prompt = request.POST.get('prompt', '').strip()
            diagram_type = request.POST.get('diagram_type', '').strip()
            
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
            
            # Create session
            session = Session.objects.create(
                prompt=prompt,
                diagram_type=diagram_type,
                status='processing',
                user_ip=self._get_client_ip(request),
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
            
            if error:
                session.status = 'failed'
                session.error_message = error
                session.save()
                return
            
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


class DiagramDisplayView(DetailView):
    """
    Display generated diagram
    """
    model = Session
    template_name = 'diagrams/display.html'
    context_object_name = 'session'
    pk_url_kwarg = 'session_id'
    
    def get_context_data(self, **kwargs):
        """Add additional context"""
        context = super().get_context_data(**kwargs)
        session = self.get_object()
        
        # Get debug mode setting
        from .models import AppSettings
        app_settings = AppSettings.load()
        
        context.update({
            'diagram_type_display': AppConstants.DIAGRAM_TYPE_DISPLAY.get(
                session.diagram_type, session.diagram_type.upper()
            ),
            'debug_mode': app_settings.mermaid_debug_mode,
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
        })
        return context


class DownloadView(View):
    """Download diagram as image or code"""
    
    def get(self, request, session_id):
        try:
            session = Session.objects.get(id=session_id)
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
                from django.shortcuts import render
                return render(request, 'diagrams/download.html', context)
                
        except Session.DoesNotExist:
            return HttpResponse("Diagram not found", status=404)

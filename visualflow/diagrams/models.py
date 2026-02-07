from django.db import models
from django.utils import timezone
from config.constants import AppConstants
import uuid


class AppSettings(models.Model):
    """
    Global application settings (Singleton model)
    """
    mermaid_debug_mode = models.BooleanField(
        default=False,
        help_text="Enable debug mode to show Mermaid code in diagram display"
    )
    
    class Meta:
        verbose_name = "App Settings"
        verbose_name_plural = "App Settings"
    
    def save(self, *args, **kwargs):
        """Ensure only one instance exists"""
        self.pk = 1
        super().save(*args, **kwargs)
    
    def delete(self, *args, **kwargs):
        """Prevent deletion"""
        pass
    
    @classmethod
    def load(cls):
        """Load settings (create if doesn't exist)"""
        obj, created = cls.objects.get_or_create(pk=1)
        return obj
    
    def __str__(self):
        return "Application Settings"


class Contact(models.Model):
    name = models.CharField(max_length=100)
    email = models.EmailField()
    subject = models.CharField(max_length=200)
    message = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.name} - {self.subject}"


class Session(models.Model):
    """
    Model to store user sessions with prompts, diagram types, and generated UML code
    """
    id = models.UUIDField(
        primary_key=True,
        default=uuid.uuid4,
        editable=False,
        help_text="Unique identifier for the session"
    )
    
    prompt = models.TextField(
        help_text="User's textual prompt for diagram generation",
        max_length=2000
    )
    
    diagram_type = models.CharField(
        max_length=20,
        choices=[(value, key) for key, value in AppConstants.DIAGRAM_TYPES.items()],
        help_text="Type of diagram to generate"
    )
    
    generated_uml = models.TextField(
        help_text="Generated Mermaid.js code",
        blank=True,
        null=True
    )
    
    diagram_svg = models.TextField(
        help_text="Generated SVG diagram content",
        blank=True,
        null=True
    )
    
    status = models.CharField(
        max_length=20,
        choices=[
            ('pending', 'Pending'),
            ('processing', 'Processing'),
            ('completed', 'Completed'),
            ('failed', 'Failed')
        ],
        default='pending',
        help_text="Status of diagram generation"
    )
    
    error_message = models.TextField(
        help_text="Error message if generation failed",
        blank=True,
        null=True
    )
    
    created_at = models.DateTimeField(
        default=timezone.now,
        help_text="When the session was created"
    )
    
    updated_at = models.DateTimeField(
        auto_now=True,
        help_text="When the session was last updated"
    )
    
    # Optional user association (for future user management)
    user_ip = models.GenericIPAddressField(
        help_text="IP address of the user",
        blank=True,
        null=True
    )
    
    user_agent = models.TextField(
        help_text="User agent string",
        blank=True,
        null=True
    )
    
    class Meta:
        ordering = ['-created_at']
        verbose_name = "Diagram Session"
        verbose_name_plural = "Diagram Sessions"
        indexes = [
            models.Index(fields=['created_at']),
            models.Index(fields=['diagram_type']),
            models.Index(fields=['status']),
        ]
    
    def __str__(self):
        return f"Session {self.id} - {self.diagram_type} - {self.status}"
    
    @property
    def prompt_preview(self):
        """Return a truncated version of the prompt for display"""
        if len(self.prompt) > 100:
            return f"{self.prompt[:100]}..."
        return self.prompt
    
    @property
    def is_completed(self):
        """Check if the session is completed successfully"""
        return self.status == 'completed' and self.generated_uml
    
    @property
    def has_diagram(self):
        """Check if the session has generated diagram content"""
        return bool(self.diagram_svg)
    
    def save(self, *args, **kwargs):
        """Override save to perform validation"""
        # Update status based on content
        if self.generated_uml and not self.error_message:
            if self.status == 'pending' or self.status == 'processing':
                self.status = 'completed'
        elif self.error_message:
            self.status = 'failed'
        
        super().save(*args, **kwargs)


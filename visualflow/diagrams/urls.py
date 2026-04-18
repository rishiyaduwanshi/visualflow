"""
URL configuration for diagrams app
"""

from django.urls import path
from . import views

app_name = 'diagrams'

urlpatterns = [
    path('', views.HomeView.as_view(), name='home'),
    path('signup/', views.SignUpView.as_view(), name='signup'),
    path('login/', views.UserLoginView.as_view(), name='login'),
    path('logout/', views.UserLogoutView.as_view(), name='logout'),
    path('generate/', views.GenerateDiagramView.as_view(), name='generate'),
    path('repair/<uuid:session_id>/', views.RepairDiagramView.as_view(), name='repair'),
    path('delete/<uuid:diagram_id>/', views.delete_diagram, name='delete_diagram'),
    path('display/<uuid:session_id>/', views.DiagramDisplayView.as_view(), name='display'),
    path('download/<uuid:session_id>/', views.DownloadView.as_view(), name='download'),
    path('contact/', views.handleContactForm, name='contact'),
    path('history/', views.SessionHistoryView.as_view(), name='history'),
]
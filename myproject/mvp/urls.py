from django.urls import path, include
from . import views
from django.views.generic.edit import CreateView
from rest_framework.routers import DefaultRouter
from .views import (
    Mention_percentageViewSet,
    dashboard_data_api,
    dashboard_view,
    RegisteringView,
)
from django.contrib.auth import views as auth_views
app_name = 'mvp'
router = DefaultRouter()
router.register(r'brand-percentages', Mention_percentageViewSet)
urlpatterns = [
    path('', include(router.urls)),
    path('dashboard-data/', dashboard_data_api, name='dashboard-data'),
    path('dashboard/', dashboard_view, name='dashboard'),
    path('orders/', views.order_list, name='order_list'),
    path('orders/create/', views.create_order, name='create_order'),
    path('orders/<int:order_id>/toggle-light/', views.toggle_light, name='toggle_light'),
    path('notifications/', views.notification_list, name='notification_list'),
    path('notifications/unread-count/', views.unread_notification_count, name='unread_notification_count'),
    path('notifications/<int:notification_id>/mark-read/', views.mark_notification_read, name='mark_notification_read'),
    path('redirect-to-create-order/', views.redirect_to_create_order, name='redirect_to_create_order'),
    path('accounts/', include('django.contrib.auth.urls')),
    path('accounts/login/', auth_views.LoginView.as_view(template_name='registration/login.html'), name='login'),
    path('accounts/logout/', auth_views.LogoutView.as_view(), name='logout'),
    path('accounts/register/', RegisteringView.as_view(), name='register'),
    path('accounts/password_change/', auth_views.PasswordChangeView.as_view(template_name='registration/password_change_form.html'), name='password_change'),
    path('accounts/password_change/done/', auth_views.PasswordChangeDoneView.as_view(template_name='registration/password_change_done.html'), name='password_change_done'),
    path('accounts/auth-check/', views.auth_check, name='auth_check')
]
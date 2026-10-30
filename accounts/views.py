"""Registration, login, and logout.

Uses Django's authentication system (authenticate/login/logout) so password
hashing, session handling, and credential checks are framework-standard.
"""

from django.contrib import messages
from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.decorators import login_required
from django.shortcuts import redirect, render
from django.views.decorators.http import require_http_methods

from .forms import LoginForm, RegistrationForm


def dashboard_url_for(user) -> str:
    """Send each kind of user to the dashboard that fits them best."""
    if user.is_staff:
        return 'dashboard:admin_dashboard'
    if hasattr(user, 'donor_profile'):
        return 'donors:donor_dashboard'
    return 'blood_requests:my_requests'


def register(request):
    if request.user.is_authenticated:
        return redirect(dashboard_url_for(request.user))

    if request.method == 'POST':
        form = RegistrationForm(request.POST)
        if form.is_valid():
            user = form.save()
            login(request, user)
            messages.success(
                request,
                f'Welcome, {user.username}! Your account has been created.'
            )
            return redirect('blood_requests:my_requests')
        messages.error(request, 'Please fix the errors below.')
    else:
        form = RegistrationForm()
    return render(request, 'accounts/register.html', {'form': form})


@require_http_methods(['GET', 'POST'])
def login_view(request):
    if request.user.is_authenticated:
        return redirect(dashboard_url_for(request.user))

    if request.method == 'POST':
        form = LoginForm(request.POST)
        if form.is_valid():
            user = authenticate(
                request,
                username=form.cleaned_data['username'],
                password=form.cleaned_data['password'],
            )
            if user is not None:
                login(request, user)
                messages.success(request, f'Welcome back, {user.username}!')
                # ?next= wins, otherwise send them to a fitting dashboard.
                next_url = request.GET.get('next') or request.POST.get('next')
                if next_url:
                    return redirect(next_url)
                return redirect(dashboard_url_for(user))
        # Same message for wrong username/password: do not reveal which failed.
        messages.error(request, 'Invalid username or password.')
    else:
        form = LoginForm()
    return render(request, 'accounts/login.html', {
        'form': form,
        'next': request.GET.get('next', ''),
    })


@login_required
@require_http_methods(['POST'])
def logout_view(request):
    logout(request)
    messages.info(request, 'You have been logged out.')
    return redirect('dashboard:home')

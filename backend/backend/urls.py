"""
URL configuration for backend project.

The `urlpatterns` list routes URLs to views. For more information please see:
    https://docs.djangoproject.com/en/5.2/topics/http/urls/
Examples:
Function views
    1. Add an import:  from my_app import views
    2. Add a URL to urlpatterns:  path('', views.home, name='home')
Class-based views
    1. Add an import:  from other_app.views import Home
    2. Add a URL to urlpatterns:  path('', Home.as_view(), name='home')
Including another URLconf
    1. Import the include() function: from django.urls import include, path
    2. Add a URL to urlpatterns:  path('blog/', include('blog.urls'))
"""
from django.urls import include, path
from testing import views
from django.contrib.auth import views as auth_views
from django.views.generic.base import RedirectView
from django.contrib import admin
from testing.views import RegisterView, custom_login

urlpatterns = [
    path('admin/', admin.site.urls),

    # Главная страница с редиректом в зависимости от роли
    path('', views.HomeView.as_view(), name='home'),
    
    # Аутентификация
    path('login/', custom_login, name='login'),
    # path('login/', auth_views.LoginView.as_view(template_name='testing/auth/login.html'), name='login'),
    path('logout/', auth_views.LogoutView.as_view(), name='logout'),
    # path('register/', views.RegisterView.as_view(), name='register'),
    path('register/', RegisterView.as_view(), name='register'),

    
    # Профиль пользователя
    path('profile/', views.ProfileView.as_view(), name='profile'),
    
    # Управление группами (для преподавателей)
    path('groups/', views.StudyGroupListView.as_view(), name='group-list'),
    path('groups/create/', views.StudyGroupCreateView.as_view(), name='group-create'),
    path('groups/<int:pk>/', views.StudyGroupDetailView.as_view(), name='group-detail'),
    path('groups/<int:pk>/update/', views.StudyGroupUpdateView.as_view(), name='group-update'),  # Добавьте эту строку
    path('groups/<int:pk>/add-student/', views.AddStudentToGroupView.as_view(), name='group-add-student'),
    
    # Тесты
    path('tests/', views.TestListView.as_view(), name='test-list'),
    path('tests/create/', views.TestCreateView.as_view(), name='test-create'),
    path('tests/<int:pk>/', views.TestDetailView.as_view(), name='test-detail'),
    path('tests/<int:pk>/edit/', views.TestUpdateView.as_view(), name='test-update'),
    path('tests/<int:pk>/assign/', views.TestAssignView.as_view(), name='test-assign'),

    # Вопросы
    path('tests/<int:test_pk>/questions/add/', views.QuestionCreateView.as_view(), name='question-create'),
    path('questions/<int:pk>/edit/', views.QuestionUpdateView.as_view(), name='question-update'),
    path('questions/<int:pk>/delete/', views.QuestionDeleteView.as_view(), name='question-delete'),
    
    # Ответы
    path('questions/<int:question_pk>/answers/add/', views.AnswerOptionCreateView.as_view(), name='answer-create'),
    path('answers/<int:pk>/edit/', views.AnswerOptionUpdateView.as_view(), name='answer-update'),
    path('answers/<int:pk>/delete/', views.AnswerOptionDeleteView.as_view(), name='answer-delete'),

    # Прохождение теста
    path('assigned-tests/', views.AssignedTestListView.as_view(), name='assigned-test-list'),
    path('test/<int:assignment_pk>/take/', views.TestTakingView.as_view(), name='test-taking'),
    path('test/<int:assignment_pk>/submit/', views.TestSubmitView.as_view(), name='test-submit'),
    
    # Результаты
    path('results/', views.TestResultListView.as_view(), name='result-list'),
    path('results/<int:pk>/', views.TestResultDetailView.as_view(), name='result-detail'),
    path('group/<int:group_pk>/results/', views.GroupResultsView.as_view(), name='group-results'),
    
    # API endpoints
    # path('api/', include('backend.api_urls')),  # Выделить API в отдельный файл

    path('answers/<int:pk>/evaluate/', views.EvaluateAnswerView.as_view(), name='evaluate-answer'),

    # Автоматическое завершение теста
    path('test/<int:assignment_pk>/auto-submit/', views.AutoSubmitTestView.as_view(), name='test-auto-submit'),
]
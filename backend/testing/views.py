from django.shortcuts import render, redirect, get_object_or_404
from django.views.generic import (
    ListView, DetailView, CreateView, UpdateView, DeleteView, FormView, TemplateView
)
from django.contrib.auth.mixins import LoginRequiredMixin, UserPassesTestMixin
from django.contrib.auth.forms import UserCreationForm
from django.contrib.auth import login, authenticate
from django.urls import reverse_lazy
from django import forms, views
from django.http import Http404, JsonResponse
from django.utils import timezone
from django.core.exceptions import ValidationError
from datetime import timedelta
from rest_framework.views import APIView
from .forms import CustomUserCreationForm, CustomAuthenticationForm, UserProfileForm, AnswerForm, AnswerOptionForm # Добавили импорт
from django.views.decorators.csrf import csrf_protect
from django.db.models import Q
from django.db.models import F, FloatField, ExpressionWrapper, Case, When, Value, IntegerField, Count, Exists, OuterRef
from django.core.paginator import Paginator, EmptyPage, PageNotAnInteger
from django.contrib import messages
from django.db.models import Subquery # Вот тут не надо делать Z-назад !!!
from django.views import View  # Добавляем этот импорт
from .models import TestResult
from .models import *

# Миксины для проверки прав доступа
class TeacherRequiredMixin(UserPassesTestMixin):
    def test_func(self):
        return self.request.user.role == 'teacher'

class StudentRequiredMixin(UserPassesTestMixin):
    def test_func(self):
        return self.request.user.role == 'student'

# Главная страница
class HomeView(LoginRequiredMixin, TemplateView):
    template_name = 'testing/home.html'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        if self.request.user.role == 'teacher':
            # 10 последних групп, отсортированных по дате создания (новые сначала)
            context['groups'] = StudyGroup.objects.filter(
                teacher=self.request.user
            ).order_by('-created_at')[:5]
            
            # 10 последних тестов, отсортированных по дате создания
            context['tests'] = Test.objects.filter(
                created_by=self.request.user
            ).order_by('-created_at')[:5]
            
            # 10 последних результатов, требующих проверки
            context['results_to_review'] = TestResult.objects.filter(
                test__created_by=self.request.user,
                status='needs_review'
            ).order_by('-completed_at')[:10]
        else:
            # 10 ближайших назначенных тестов (по дедлайну)
            context['assigned_tests'] = TestAssignment.objects.filter(
                group__students__student=self.request.user,
                deadline__gte=timezone.now()
            ).order_by('deadline')[:10]
        return context


# Аутентификация
class RegisterView(CreateView):
    form_class = CustomUserCreationForm
    template_name = 'testing/auth/register.html'
    success_url = reverse_lazy('home')
    
    def form_valid(self, form):
        response = super().form_valid(form)
        # Автоматический вход после регистрации
        email = form.cleaned_data.get('email')
        password = form.cleaned_data.get('password1')
        user = authenticate(email=email, password=password)
        login(self.request, user)
        return response

@csrf_protect
def custom_login(request):
    if request.method == 'POST':
        form = CustomAuthenticationForm(request.POST)
        if form.is_valid():
            login(request, form.user)
            return redirect('home')
    else:
        form = CustomAuthenticationForm()
    
    return render(request, 'testing/auth/login.html', {'form': form})

# Профиль
class ProfileView(LoginRequiredMixin, UpdateView):
    model = User
    form_class = UserProfileForm
    template_name = 'testing/profile.html'
    success_url = reverse_lazy('profile')

    def get_object(self):
        return self.request.user

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        user = self.request.user

        # Безопасное получение имени
        first_name = user.first_name or ''
        last_name = user.last_name or ''
        display_name = (f"{last_name} {first_name}".strip() or user.email)

        context['welcome_message'] = f"Добро пожаловать, {display_name}!"
        return context


# Группы (для преподавателей)
class StudyGroupListView(LoginRequiredMixin, TeacherRequiredMixin, ListView):
    model = StudyGroup
    template_name = 'testing/groups/group_list.html'

    def get_queryset(self):
        return StudyGroup.objects.filter(teacher=self.request.user)
    
class StudyGroupCreateView(LoginRequiredMixin, TeacherRequiredMixin, CreateView):
    model = StudyGroup
    fields = ['name']
    template_name = 'testing/groups/group_form.html'
    success_url = reverse_lazy('group-list')

    def form_valid(self, form):
        form.instance.teacher = self.request.user
        return super().form_valid(form)

class StudyGroupDetailView(LoginRequiredMixin, TeacherRequiredMixin, DetailView):
    model = StudyGroup
    template_name = 'testing/groups/group_detail.html'
    paginate_by = 10  # Количество тестов на странице

    def get_queryset(self):
        return StudyGroup.objects.filter(teacher=self.request.user)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        now = timezone.now()
        
        # Получаем всех студентов группы
        context['students'] = User.objects.filter(
            student_groups__group=self.object
        ).order_by('last_name', 'first_name')
        
        # Получаем назначенные тесты с правильной сортировкой
        assigned_tests = TestAssignment.objects.filter(
            group=self.object
        ).annotate(
            is_past_deadline=Case(
                When(deadline__lt=now, then=Value(1)),
                default=Value(0),
                output_field=IntegerField()
            )
        ).order_by('is_past_deadline', 'deadline') # Сортируем по сроку и дедлайну (типа те, которые уже просрочены по дедлайну, в конец)
        
        paginator = Paginator(assigned_tests, self.paginate_by)
        page = self.request.GET.get('page')
        
        try:
            assigned_tests_page = paginator.page(page)
        except PageNotAnInteger:
            assigned_tests_page = paginator.page(1)
        except EmptyPage:
            assigned_tests_page = paginator.page(paginator.num_pages)
            
        context['assigned_tests'] = assigned_tests_page
        context['current_time'] = now
        return context

class AddStudentToGroupView(LoginRequiredMixin, TeacherRequiredMixin, FormView):
    template_name = 'testing/groups/add_student.html'
    form_class = forms.Form

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        group = get_object_or_404(
            StudyGroup, 
            pk=self.kwargs['pk'], 
            teacher=self.request.user
        )
        
        # Получаем студентов, которые еще не в этой группе
        existing_students = group.students.all()
        available_students = User.objects.filter(
            role='student'
        ).exclude(
            pk__in=existing_students.values_list('pk', flat=True)
        ).order_by('last_name', 'first_name', 'email')  # Сортировка по фамилии, имени и email
        
        context.update({
            'group': group,
            'available_students': available_students
        })
        return context

    def form_valid(self, form):
        group = get_object_or_404(
            StudyGroup, 
            pk=self.kwargs['pk'], 
            teacher=self.request.user
        )
        student_id = self.request.POST.get('student_id')
        student = get_object_or_404(User, pk=student_id, role='student')
        
        StudentGroup.objects.get_or_create(student=student, group=group)
        return redirect('group-detail', pk=group.pk)
    
class StudyGroupUpdateView(LoginRequiredMixin, TeacherRequiredMixin, UpdateView):
    model = StudyGroup
    fields = ['name']
    template_name = 'testing/groups/group_form.html'
    
    def get_queryset(self):
        return StudyGroup.objects.filter(teacher=self.request.user)
    
    def get_success_url(self):
        return reverse('group-detail', kwargs={'pk': self.object.pk})

# Тесты
class TestListView(LoginRequiredMixin, TeacherRequiredMixin, ListView):
    model = Test
    template_name = 'testing/tests/test_list.html'
    paginate_by = 6  #Пагинация по 6 тестов на страницу

    def get_queryset(self):
        queryset = Test.objects.filter(created_by=self.request.user)

        # Поиск
        q = self.request.GET.get('q')
        if q:
            queryset = queryset.filter(title__icontains=q)

        # Сортировка
        sort = self.request.GET.get('sort')
        if sort == 'title':
            queryset = queryset.order_by('title')
        elif sort == 'created':
            queryset = queryset.order_by('-created_at')
        elif sort == 'created_old':
            queryset = queryset.order_by('created_at')

        return queryset
    
class TestCreateView(LoginRequiredMixin, TeacherRequiredMixin, CreateView):
    model = Test
    fields = ['title', 'description', 'time_limit']
    template_name = 'testing/tests/test_form.html'
    success_url = reverse_lazy('test-list')

    def form_valid(self, form):
        form.instance.created_by = self.request.user
        return super().form_valid(form)

class TestDetailView(LoginRequiredMixin, DetailView):
    model = Test
    template_name = 'testing/tests/test_detail.html'

    def get_queryset(self):
        if self.request.user.role == 'teacher':
            return Test.objects.filter(created_by=self.request.user)
        return Test.objects.filter(assignments__group__students__student=self.request.user)

class TestUpdateView(LoginRequiredMixin, TeacherRequiredMixin, UpdateView):
    model = Test
    fields = ['title', 'description', 'time_limit']
    template_name = 'testing/tests/test_form.html'

    def get_success_url(self):
        return reverse_lazy('test-detail', kwargs={'pk': self.object.pk})

class TestAssignView(LoginRequiredMixin, TeacherRequiredMixin, CreateView):
    model = TestAssignment
    fields = ['group', 'deadline']
    template_name = 'testing/tests/test_assign.html'

    def get_test(self):
        return get_object_or_404(Test, pk=self.kwargs['pk'], created_by=self.request.user)

    def get_form(self, form_class=None):
        form = super().get_form(form_class)
        form.fields['group'].queryset = StudyGroup.objects.filter(teacher=self.request.user)
        return form

    def form_valid(self, form):
        test = self.get_test()
        group = form.cleaned_data['group']
        deadline = form.cleaned_data['deadline']
        
        # Проверяем, существует ли уже такое назначение
        existing_assignment = TestAssignment.objects.filter(
            test=test,
            group=group
        ).first()
        
        if existing_assignment:
            # Если назначение уже существует - обновляем дедлайн
            existing_assignment.deadline = deadline
            existing_assignment.save()
            messages.success(self.request, f'Срок выполнения теста для группы "{group.name}" обновлен')
        else:
            # Если не существует - создаем новое назначение
            form.instance.test = test
            messages.success(self.request, f'Тест успешно назначен группе "{group.name}"')
            return super().form_valid(form)
        
        return redirect(self.get_success_url())

    def form_invalid(self, form):
        messages.error(self.request, 'Ошибка при назначении теста. Проверьте данные.')
        return super().form_invalid(form)
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['test'] = self.get_test()
        return context

    def get_success_url(self):
        return reverse('test-detail', kwargs={'pk': self.kwargs['pk']})

# Вопросы
class QuestionCreateView(LoginRequiredMixin, TeacherRequiredMixin, CreateView):
    model = Question
    fields = ['text', 'question_type', 'order']
    template_name = 'testing/questions/question_form.html'

    def get_test(self):
        return get_object_or_404(Test, pk=self.kwargs['test_pk'], created_by=self.request.user)

    def form_valid(self, form):
        form.instance.test = self.get_test()
        return super().form_valid(form)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        test = self.get_test()
        context['test'] = test  # Добавляем объект теста в контекст
        return context

    def get_success_url(self):
        return reverse('test-detail', kwargs={'pk': self.kwargs['test_pk']})

class QuestionUpdateView(LoginRequiredMixin, TeacherRequiredMixin, UpdateView):
    model = Question
    fields = ['text', 'question_type', 'order']
    template_name = 'testing/questions/question_form.html'

    def get_queryset(self):
        return Question.objects.filter(test__created_by=self.request.user)

    def get_success_url(self):
        # Перенаправляем на страницу теста
        return reverse('test-detail', kwargs={'pk': self.object.test.pk})
        
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['test_pk'] = self.object.test.pk
        context['answer_options'] = self.object.answer_options.all()
        context['add_answer_url'] = reverse('answer-create', kwargs={'question_pk': self.object.pk})
        return context

class QuestionDeleteView(LoginRequiredMixin, TeacherRequiredMixin, DeleteView):
    model = Question
    template_name = 'testing/questions/question_confirm_delete.html'

    def get_queryset(self):
        return Question.objects.filter(test__created_by=self.request.user)

    def get_success_url(self):
        return reverse_lazy('test-detail', kwargs={'pk': self.object.test.pk})

# Прохождение теста
class AssignedTestListView(LoginRequiredMixin, StudentRequiredMixin, ListView):
    model = TestAssignment
    template_name = 'testing/tests/assigned_test_list.html'
    paginate_by = 5

    def get_queryset(self):
        now = timezone.now()
        return TestAssignment.objects.filter(
            group__students__student=self.request.user,
            deadline__gte=now
        ).select_related('test', 'group').annotate(  # Все методы в одной строке
            has_result=Exists(
                TestResult.objects.filter(
                    test=OuterRef('test'),
                    student=self.request.user
                )
            ),
            result_id=Subquery(
                TestResult.objects.filter(
                    test=OuterRef('test'),
                    student=self.request.user
                ).order_by('-completed_at').values('pk')[:1]
            )
        ).order_by('has_result', 'deadline')

class TestTakingView(LoginRequiredMixin, StudentRequiredMixin, FormView):
    template_name = 'testing/tests/test_taking.html'
    form_class = AnswerForm

    def get_assignment(self):
        assignment_pk = self.kwargs.get('assignment_pk')
        return get_object_or_404(
            TestAssignment,
            pk=assignment_pk,
            group__students__student=self.request.user
        )

    def get_initial(self):
        initial = super().get_initial()
        session_data = self.request.session.get('test_answers', {})
        if str(session_data.get('assignment_pk')) == str(self.kwargs['assignment_pk']):
            initial.update(session_data.get('answers', {}))
        return initial

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        assignment = self.get_assignment()
        context['assignment'] = assignment
        
        # Получаем или создаем запись о начале теста
        test_start, created = TestStartTime.objects.get_or_create(
            student=self.request.user,
            assignment=assignment,
            defaults={'start_time': timezone.now()}
        )
        
        # Рассчитываем оставшееся время
        if assignment.test.time_limit:
            elapsed_seconds = (timezone.now() - test_start.start_time).total_seconds()
            remaining_seconds = max(0, assignment.test.time_limit * 60 - elapsed_seconds)
            context['time_left'] = remaining_seconds
            context['start_time'] = test_start.start_time.isoformat()
        
        return context

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        assignment = self.get_assignment()
        if not assignment:
            raise Http404("Назначение теста не найдено")
        kwargs['questions'] = assignment.test.questions.all().order_by('order')
        return kwargs

    def get_form(self, form_class=None):
        form = super().get_form(form_class)
        assignment = self.get_assignment()
        questions = assignment.test.questions.all().order_by('order')
        
        for question in questions:
            field_name = f"question_{question.id}"
            if question.question_type == 'text':
                form.fields[field_name] = forms.CharField(
                    label=question.text,
                    widget=forms.Textarea,
                    required=False
                )
            else:
                choices = [(opt.id, opt.text) for opt in question.answer_options.all()]
                if question.question_type == 'single':
                    form.fields[field_name] = forms.ChoiceField(
                        label=question.text,
                        choices=choices,
                        widget=forms.RadioSelect,
                        required=False
                    )
                else:
                    form.fields[field_name] = forms.MultipleChoiceField(
                        label=question.text,
                        choices=choices,
                        widget=forms.CheckboxSelectMultiple,
                        required=False
                    )
        return form

    def form_valid(self, form):
        # Сохраняем ответы в сессии для подтверждения
        self.request.session['test_answers'] = {
            'assignment_pk': self.kwargs['assignment_pk'],
            'answers': form.cleaned_data,
            'start_time': str(timezone.now())
        }
        return redirect('test-submit', assignment_pk=self.kwargs['assignment_pk'])

class TestSubmitView(LoginRequiredMixin, StudentRequiredMixin, TemplateView):
    template_name = 'testing/tests/test_submit.html'

    def get_assignment(self):
        return get_object_or_404(
            TestAssignment,
            pk=self.kwargs['assignment_pk'],
            group__students__student=self.request.user
        )

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        assignment = self.get_assignment()
        test = assignment.test

        session_data = self.request.session.get('test_answers', {})
        raw_answers = session_data.get('answers', {})

        #print("🔍 raw_answers из сессии:", raw_answers)  # Выводим, что пришло из сессии

        # Преобразуем ключи в "question_{id}" -> bool
        processed_answers = {}
        for question in test.questions.all():
            key = f"question_{question.id}"
            value = raw_answers.get(key)

            if value is not None and value != '' and value != []:
                processed_answers[key] = True
            else:
                processed_answers[key] = False

            #print(f"➡️  Обработка {key}: значение = {value!r}, сохранен = {processed_answers[key]}")  # Детальный вывод

        #print("✅ processed_answers:", processed_answers)  # Финальный результат

        context.update({
            'test': test,
            'questions': test.questions.all().order_by('order'),
            'answers': processed_answers,
            'assignment': assignment
        })
        return context


    def post(self, request, *args, **kwargs):
        session_data = request.session.get('test_answers', {})
        
        if not session_data or str(session_data.get('assignment_pk')) != str(kwargs['assignment_pk']):
            raise ValidationError("Данные теста не найдены")

        assignment = self.get_assignment()
        test = assignment.test
        answers = session_data.get('answers', {})

        test_result, created = TestResult.objects.get_or_create(
            student=self.request.user,
            test=test,
            defaults={'score': 0, 'status': 'completed'}
        )

        needs_review = False

        if created:
            for question in test.questions.all():
                field_name = f"question_{question.id}"
                answer = answers.get(field_name)

                student_answer = StudentAnswer.objects.create(
                    result=test_result,
                    question=question,
                    answer_text=answer if question.question_type == 'text' else None
                )

                if question.question_type == 'text':
                    needs_review = True
                elif answer:
                    if question.question_type == 'single':
                        answer = [answer]

                    selected_options = AnswerOption.objects.filter(
                        id__in=answer,
                        question=question
                    )
                    student_answer.selected_options.set(selected_options)

        else:
            # Обновляем только текстовые ответы
            for question in test.questions.filter(question_type='text'):
                field_name = f"question_{question.id}"
                answer_text = answers.get(field_name, '')

                student_answer, created = StudentAnswer.objects.get_or_create(
                    result=test_result,
                    question=question,
                    defaults={'answer_text': answer_text}
                )
                if not created:
                    student_answer.answer_text = answer_text
                    student_answer.save()
                needs_review = True

        # Обновляем статус
        test_result.status = 'needs_review' if needs_review else 'completed'
        
        # Пересчёт баллов (включая вручную выставленные баллы за текстовые вопросы)
        test_result.recalculate_score()

        if 'test_answers' in request.session:
            del request.session['test_answers']

        return redirect('result-detail', pk=test_result.pk)


# Результаты

class TestResultListView(LoginRequiredMixin, ListView):
    model = TestResult
    template_name = 'testing/results/result_list.html'
    paginate_by = 10

    def get_queryset(self):
        user = self.request.user
        queryset = TestResult.objects.all()

        if user.role == 'teacher':
            queryset = queryset.filter(test__created_by=user)

            # Фильтрация по группе
            group_id = self.request.GET.get('group')
            if group_id:
                queryset = queryset.filter(
                    test__assignments__group_id=group_id
                )
        else:
            queryset = queryset.filter(student=user)

        # Поиск
        q = self.request.GET.get('q')
        if q:
            queryset = queryset.filter(test__title__icontains=q)

        # Сортировка
        sort = self.request.GET.get('sort')
        if sort == 'score':
            queryset = queryset.filter(test__max_score__gt=0)
            queryset = queryset.annotate(
                percent_score=ExpressionWrapper(
                    F('score') * 1.0 / F('test__max_score'),
                    output_field=FloatField()
                )
            ).order_by('-percent_score')
        elif sort == 'date':
            queryset = queryset.order_by('-completed_at')
        elif sort == 'name':
            queryset = queryset.order_by('test__title')
        elif sort == 'status':
            queryset = queryset.annotate(
                needs_review_first=Case(
                    When(status='needs_review', then=Value(0)),
                    default=Value(1),
                    output_field=IntegerField()
                )
            ).order_by('needs_review_first', '-completed_at')

        return queryset.distinct()

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        if self.request.user.role == 'teacher':
            # Все группы, которым преподаватель назначал тесты
            context['groups'] = StudyGroup.objects.filter(
                assigned_tests__test__created_by=self.request.user
            ).distinct()
        return context
    
class TestResultDetailView(LoginRequiredMixin, DetailView):
    model = TestResult
    template_name = 'testing/results/result_detail.html'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        obj = self.get_object()
        
        # Получаем группу, к которой принадлежит тест
        context['group'] = obj.test.assignments.first().group if obj.test.assignments.exists() else None
        
        try:
            context['percentage'] = round(obj.score / obj.test.max_score * 100)
        except ZeroDivisionError:
            context['percentage'] = 0
        return context

    def get_queryset(self):
        if self.request.user.role == 'teacher':
            return TestResult.objects.filter(test__created_by=self.request.user)
        return TestResult.objects.filter(student=self.request.user)

class GroupResultsView(LoginRequiredMixin, TeacherRequiredMixin, ListView):
    model = TestResult
    template_name = 'testing/results/group_results.html'

    def get_queryset(self):
        group = get_object_or_404(StudyGroup, pk=self.kwargs['group_pk'], teacher=self.request.user)
        return TestResult.objects.filter(
            student__student_groups__group=group
        ).select_related('student', 'test')

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['group'] = get_object_or_404(StudyGroup, pk=self.kwargs['group_pk'])
        return context

# Оценка текстовых ответов
# views.py
class EvaluateAnswerView(LoginRequiredMixin, TeacherRequiredMixin, UpdateView):
    model = StudentAnswer
    fields = ['score']
    template_name = 'testing/results/evaluate_answer.html'

    def get_queryset(self):
        return StudentAnswer.objects.filter(
            question__question_type='text',
            result__test__created_by=self.request.user,
            result__status='needs_review'
        )

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['question'] = self.object.question
        context['student'] = self.object.result.student
        return context

    def form_valid(self, form):
        response = super().form_valid(form)
        # Вместо простого суммирования вызываем пересчет баллов
        result = self.object.result
        result.recalculate_score()  # Используем метод пересчета
        if not result.answers.filter(question__question_type='text', score=0).exists():
            result.status = 'completed'
        result.save()
        return response

    def get_success_url(self):
        return reverse_lazy('result-detail', kwargs={'pk': self.object.result.pk})
    
# API Views
class QuestionOptionsAPIView(LoginRequiredMixin, APIView):
    def get(self, request, pk):
        question = get_object_or_404(Question, pk=pk)
        options = question.answer_options.all()
        data = [{'id': o.id, 'text': o.text} for o in options]
        return JsonResponse(data, safe=False)
    
# Для добавления ответов на вопросы для учителя
class AnswerOptionCreateView(LoginRequiredMixin, TeacherRequiredMixin, CreateView):
    model = AnswerOption
    fields = ['text', 'is_correct']
    template_name = 'testing/answers/answer_form.html'

    def setup(self, request, *args, **kwargs):
        super().setup(request, *args, **kwargs)
        self.question = get_object_or_404(
            Question,
            pk=self.kwargs['question_pk'],
            test__created_by=self.request.user
        )

    def get_form(self, form_class=None):
        form = super().get_form(form_class)
        # Для текстовых вопросов скрываем поле is_correct
        if self.question.question_type == 'text':
            form.fields['is_correct'].widget = forms.HiddenInput()
            form.fields['is_correct'].initial = False
        return form

    def form_valid(self, form):
        form.instance.question = self.question
        
        try:
            # Вызываем полную очистку с установленным вопросом
            return super().form_valid(form)
        except ValidationError as e:
            form.add_error(None, e)
            return self.form_invalid(form)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['question'] = self.question
        return context

    def get_success_url(self):
        return reverse('question-update', kwargs={'pk': self.question.pk})

class AnswerOptionUpdateView(LoginRequiredMixin, TeacherRequiredMixin, UpdateView):
    model = AnswerOption
    fields = ['text', 'is_correct']
    template_name = 'testing/answers/answeroption_form.html'

    def get_question(self):
        # Получаем вопрос из текущего объекта AnswerOption
        return self.object.question

    def get_success_url(self):
        # Используем question.pk вместо question.id для consistency
        return reverse('question-update', kwargs={'pk': self.get_question().pk})

class AnswerOptionDeleteView(LoginRequiredMixin, TeacherRequiredMixin, DeleteView):
    model = AnswerOption
    template_name = 'testing/answers/answeroption_confirm_delete.html'

    def get_queryset(self):
        return AnswerOption.objects.filter(question__test__created_by=self.request.user)

    def get_success_url(self):
        return reverse('question-update', kwargs={'pk': self.object.question.pk})


class AutoSubmitTestView(LoginRequiredMixin, StudentRequiredMixin, View):
    def post(self, request, *args, **kwargs):
        assignment = get_object_or_404(
            TestAssignment,
            pk=self.kwargs['assignment_pk'],
            group__students__student=self.request.user
        )
        test = assignment.test
        
        # Получаем данные формы из сессии
        session_data = request.session.get('test_answers', {})
        if not session_data:
            raise ValidationError("Данные теста не найдены")
        
        answers = session_data.get('answers', {})

        # Создаем или обновляем результат теста
        test_result, created = TestResult.objects.get_or_create(
            student=self.request.user,
            test=test,
            defaults={'score': 0, 'status': 'completed'}
        )

        needs_review = False

        if created:
            for question in test.questions.all():
                field_name = f"question_{question.id}"
                answer = answers.get(field_name)

                student_answer = StudentAnswer.objects.create(
                    result=test_result,
                    question=question,
                    answer_text=answer if question.question_type == 'text' else None
                )

                if question.question_type == 'text':
                    needs_review = True
                elif answer:
                    if question.question_type == 'single':
                        answer = [answer]

                    selected_options = AnswerOption.objects.filter(
                        id__in=answer,
                        question=question
                    )
                    student_answer.selected_options.set(selected_options)
        else:
            for question in test.questions.filter(question_type='text'):
                field_name = f"question_{question.id}"
                answer_text = answers.get(field_name, '')

                student_answer, created = StudentAnswer.objects.get_or_create(
                    result=test_result,
                    question=question,
                    defaults={'answer_text': answer_text}
                )
                if not created:
                    student_answer.answer_text = answer_text
                    student_answer.save()
                needs_review = True

        test_result.status = 'needs_review' if needs_review else 'completed'
        test_result.recalculate_score()

        if 'test_answers' in request.session:
            del request.session['test_answers']

        return redirect('result-detail', pk=test_result.pk)
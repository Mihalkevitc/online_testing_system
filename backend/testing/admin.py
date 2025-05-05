from django.contrib import admin
from django.utils.html import format_html
from .models import *
from django.utils import timezone

@admin.register(User)
class UserAdmin(admin.ModelAdmin):
    list_display = ('full_name', 'email', 'role', 'is_active', 'date_joined')
    list_filter = ('role', 'is_active', 'is_staff')
    search_fields = ('email', 'first_name', 'last_name')
    list_per_page = 20
    fieldsets = (
        (None, {
            'fields': ('email', 'password')
        }),
        ('Персональная информация', {
            'fields': ('last_name', 'first_name', 'role')
        }),
        ('Права доступа', {
            'fields': ('is_active', 'is_staff', 'is_superuser', 'groups', 'user_permissions')
        }),
        ('Даты', {
            'fields': ('last_login', 'date_joined'),
            'classes': ('collapse',)
        }),
    )
    
    def full_name(self, obj):
        return f"{obj.last_name} {obj.first_name}"
    full_name.short_description = 'ФИО'
    full_name.admin_order_field = 'last_name'

@admin.register(StudyGroup)
class StudyGroupAdmin(admin.ModelAdmin):
    list_display = ('name', 'teacher_link', 'student_count')
    list_select_related = ('teacher',)
    search_fields = ('name', 'teacher__last_name', 'teacher__first_name', 'teacher__email')
    list_filter = ('teacher',)
    
    def teacher_link(self, obj):
        teacher = obj.teacher
        return format_html(
            '<a href="/admin/testing/user/{}/change/">{} {}</a>',
            teacher.id,
            teacher.last_name,
            teacher.first_name
        )
    teacher_link.short_description = 'Преподаватель'
    
    def student_count(self, obj):
        return obj.students.count()
    student_count.short_description = 'Кол-во студентов'

@admin.register(StudentGroup)
class StudentGroupAdmin(admin.ModelAdmin):
    list_display = ('student_info', 'group', 'date_added')
    list_filter = ('group',)
    search_fields = ('student__last_name', 'student__first_name', 'student__email', 'group__name')
    autocomplete_fields = ('student', 'group')
    
    def student_info(self, obj):
        student = obj.student
        return f"{student.last_name} {student.first_name} ({student.email})"
    student_info.short_description = 'Студент'
    
    def date_added(self, obj):
        return obj.group.created_at if hasattr(obj.group, 'created_at') else 'N/A'
    date_added.short_description = 'Дата создания группы'

@admin.register(Test)
class TestAdmin(admin.ModelAdmin):
    list_display = ('title', 'author', 'question_count', 'time_limit', 'max_score')
    list_filter = ('created_by',)
    search_fields = ('title', 'description')
    readonly_fields = ('max_score',)
    fields = ('title', 'description', 'created_by', 'time_limit', 'max_score')
    
    def author(self, obj):
        creator = obj.created_by
        return f"{creator.last_name} {creator.first_name}"
    author.short_description = 'Автор'
    author.admin_order_field = 'created_by__last_name'
    
    def question_count(self, obj):
        return obj.questions.count()
    question_count.short_description = 'Вопросов'

# Добавляем inline-редактор для вариантов ответов
class AnswerOptionInline(admin.TabularInline):
    model = AnswerOption
    extra = 1  # Количество пустых форм для добавления
    fields = ('text', 'is_correct')
    
    def has_change_permission(self, request, obj=None):
        return True
    
    def has_delete_permission(self, request, obj=None):
        return True

@admin.register(Question)
class QuestionAdmin(admin.ModelAdmin):
    list_display = ('short_text', 'test_link', 'question_type', 'order')
    list_filter = ('question_type', 'test')
    search_fields = ('text', 'test__title')
    list_editable = ('order',)
    list_per_page = 30
    inlines = [AnswerOptionInline]  # Now it's a proper list
    actions = ['mark_as_single', 'mark_as_multiple']
    
    def mark_as_single(self, request, queryset):
        queryset.update(question_type='single')
    mark_as_single.short_description = "Сделать вопросами с одним ответом"
    
    def mark_as_multiple(self, request, queryset):
        queryset.update(question_type='multiple')
    mark_as_multiple.short_description = "Сделать вопросами с несколькими ответами"
    
    def short_text(self, obj):
        return obj.text[:100] + '...' if len(obj.text) > 100 else obj.text
    short_text.short_description = 'Текст вопроса'
    
    def test_link(self, obj):
        return format_html('<a href="/admin/testing/test/{}/change/">{}</a>',
                          obj.test.id,
                          obj.test.title)
    test_link.short_description = 'Тест'
    
    # Добавляем метод для отображения вариантов ответов в детальном просмотре
    def get_fieldsets(self, request, obj=None):
        fieldsets = super().get_fieldsets(request, obj)
        if obj:  # Только при редактировании существующего объекта
            fieldsets += (
                ('Варианты ответов', {
                    'fields': (),  # Пустое поле, так как варианты будут во вкладке
                    'description': self.format_answer_options(obj)
                }),
            )
        return fieldsets
    
    def format_answer_options(self, question):
        options = question.answer_options.all()
        if not options:
            return "<p>Нет добавленных вариантов ответа</p>"
        
        html = '<table><tr><th>Текст</th><th>Правильный</th></tr>'
        for option in options:
            html += f'<tr><td>{option.text}</td><td>{"✓" if option.is_correct else "✗"}</td></tr>'
        html += '</table>'
        return format_html(html)
    

@admin.register(AnswerOption)
class AnswerOptionAdmin(admin.ModelAdmin):
    list_display = ('short_text', 'question_link', 'test_link', 'is_correct')
    list_filter = ('is_correct', 'question__test')
    search_fields = ('text', 'question__text')
    
    def test_link(self, obj):
        return format_html('<a href="/admin/testing/test/{}/change/">{}</a>',
                          obj.question.test.id,
                          obj.question.test.title)
    test_link.short_description = 'Тест'
    
    def short_text(self, obj):
        return obj.text[:50] + '...' if len(obj.text) > 50 else obj.text
    short_text.short_description = 'Вариант ответа'
    
    def question_link(self, obj):
        return format_html('<a href="/admin/testing/question/{}/change/">{}</a>',
                          obj.question.id,
                          obj.question.text[:50] + '...')
    question_link.short_description = 'Вопрос'

@admin.register(TestAssignment)
class TestAssignmentAdmin(admin.ModelAdmin):
    list_display = ('test', 'group', 'assigned_at', 'deadline', 'is_active')
    list_filter = ('test', 'group', 'assigned_at')
    readonly_fields = ('assigned_at',)
    
    def is_active(self, obj):
        now = timezone.now()
        if obj.deadline:
            return obj.deadline > now
        return True
    is_active.boolean = True
    is_active.short_description = 'Активно'

@admin.register(TestResult)
class TestResultAdmin(admin.ModelAdmin):
    list_display = ('student_info', 'test', 'score', 'completed_at', 'success_percentage')
    list_filter = ('test', 'completed_at')
    search_fields = ('student__last_name', 'student__first_name', 'student__email', 'test__title')
    readonly_fields = ('completed_at',)
    
    def student_info(self, obj):
        student = obj.student
        return f"{student.last_name} {student.first_name} ({student.email})"
    student_info.short_description = 'Студент'
    student_info.admin_order_field = 'student__last_name'
    
    def success_percentage(self, obj):
        if obj.test.max_score > 0:
            return f"{round((obj.score / obj.test.max_score) * 100)}%"
        return "N/A"
    success_percentage.short_description = '% успеха'

@admin.register(StudentAnswer)
class StudentAnswerAdmin(admin.ModelAdmin):
    list_display = ('result_link', 'question_link', 'answer_type')
    list_filter = ('question__question_type',)
    search_fields = ('result__student__last_name', 'result__student__first_name', 'question__text')
    
    def result_link(self, obj):
        student = obj.result.student
        return format_html(
            '<a href="/admin/testing/testresult/{}/change/">{} {}</a>',
            obj.result.id,
            student.last_name,
            student.first_name
        )
    result_link.short_description = 'Студент'
    
    def question_link(self, obj):
        return format_html('<a href="/admin/testing/question/{}/change/">{}</a>',
                          obj.question.id,
                          obj.question.text[:50] + '...')
    question_link.short_description = 'Вопрос'
    
    def answer_type(self, obj):
        if obj.question.question_type == 'text':
            return 'Текстовый ответ'
        return f"Выбрано вариантов: {obj.selected_options.count()}"
    answer_type.short_description = 'Тип ответа'

# Настройки админ-панели
admin.site.site_header = "Система онлайн-тестирования"
admin.site.site_title = "Администрирование"
admin.site.index_title = "Управление системой"
from django.db import models
from django.contrib.auth.models import AbstractUser
from django.core.exceptions import ValidationError
from django.urls import reverse
from django.db.models import Max
from django.utils import timezone

class User(AbstractUser):
    ROLES = (
        ('student', 'Ученик'),
        ('teacher', 'Учитель'),
    )
    
    # Убираем username заменяем на фамилию и имя и email
    username = None
    email = models.EmailField('Email', unique=True)
    role = models.CharField(max_length=10, choices=ROLES)
    
    first_name = models.CharField('Имя', max_length=30, blank=False)  # Обязательное поле
    last_name = models.CharField('Фамилия', max_length=30, blank=False)  # Обязательное поле
    
    USERNAME_FIELD = 'email'
    REQUIRED_FIELDS = ['first_name', 'last_name']
    
    def __str__(self):
        full_name = self.get_full_name()
        return f"{full_name if full_name else self.email} ({self.get_role_display()})"
    
    def get_full_name(self):
        """
        Гарантированно возвращает строку с именем пользователя
        """
        name_parts = []
        if self.last_name:
            name_parts.append(self.last_name)
        if self.first_name:
            name_parts.append(self.first_name)
        
        full_name = ' '.join(name_parts).strip()
        return full_name if full_name else self.email
        
    def get_short_name(self):
        """Возвращает имя пользователя или email, если имя не указано"""
        return self.first_name if self.first_name else self.email
    
    class Meta:
        verbose_name = 'Пользователь'
        verbose_name_plural = 'Пользователи'
        ordering = ['last_name', 'first_name']

class StudyGroup(models.Model):
    """
    Учебная группа, к которой привязаны студенты.
    Каждая группа имеет преподавателя, который ей управляет.
    """
    name = models.CharField(max_length=100, verbose_name="Название группы")
    teacher = models.ForeignKey(
        User, 
        on_delete=models.CASCADE,  # При удалении учителя удаляются и его группы
        related_name='teacher_groups',
        limit_choices_to={'role': 'teacher'},  # Ограничение: только учителя могут быть привязаны
        verbose_name="Преподаватель"
    )
    created_at = models.DateTimeField(
        auto_now_add=True,  # Автоматически устанавливается при создании
        verbose_name="Дата создания"
    )

    def get_absolute_url(self):
        return reverse('group-detail', kwargs={'pk': self.pk})
    
    def __str__(self):
        """Строковое представление группы: название и преподаватель"""
        return f"{self.name} (Преподаватель: {self.teacher.get_full_name()})"
    
    class Meta:
        verbose_name = 'Учебная группа'
        verbose_name_plural = 'Учебные группы'
        ordering = ['name']  # Сортировка по названию группы

class StudentGroup(models.Model):
    """
    Связующая модель между студентами и группами.
    Позволяет одному студенту быть в нескольких группах,
    и одной группе содержать множество студентов.
    """
    student = models.ForeignKey(
        User, 
        on_delete=models.CASCADE,
        limit_choices_to={'role': 'student'},  # Ограничение: только студенты
        related_name='student_groups',
        verbose_name="Студент"
    )
    group = models.ForeignKey(
        StudyGroup, 
        on_delete=models.CASCADE, 
        related_name='students',
        verbose_name="Группа"
    )
    
    class Meta:
        unique_together = ('student', 'group')  # Студент может быть в группе только один раз
        verbose_name = 'Студент в группе'
        verbose_name_plural = 'Студенты в группах'
        ordering = ['group', 'student__last_name', 'student__first_name']  # Сортировка по группе, затем по фамилии и имени студента
    
    def __str__(self):
        """Строковое представление: студент в группе"""
        return f"{self.student.get_full_name()} в группе {self.group.name}"

class Test(models.Model):
    """
    Модель теста, который создается преподавателем.
    Содержит основную информацию о тесте и его настройки.
    """
    title = models.CharField(
        max_length=200,
        verbose_name="Название теста"
    )
    description = models.TextField(
        verbose_name="Описание",
        blank=True  # Описание может быть пустым
    )
    created_by = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        limit_choices_to={'role': 'teacher'},  # Только учителя могут создавать тесты
        related_name='created_tests',
        verbose_name="Создатель"
    )
    time_limit = models.IntegerField(
        null=True,
        blank=True,
        verbose_name="Лимит времени (минуты)"  # Опциональное ограничение по времени
    )
    max_score = models.IntegerField(
        default=0,
        editable=False,  # Поле вычисляется автоматически (Если для editable установлено значение False, то поле не будет отображаться для редактирования в форме заполнения)
        verbose_name="Максимальный балл"
    )
    created_at = models.DateTimeField(
        auto_now_add=True,
        verbose_name="Дата создания"
    )

    def get_absolute_url(self):
        return reverse('test-detail', kwargs={'pk': self.pk})
    
    def save(self, *args, **kwargs):
        # Сначала сохраняем тест
        super().save(*args, **kwargs)
        
        # Рассчитываем максимальный балл (1 балл за ЛЮБОЙ вопрос, включая текстовые)
        new_max_score = self.questions.count()  # Просто считаем общее количество вопросов
        
        # Обновляем max_score, если он изменился
        if self.max_score != new_max_score:
            self.max_score = new_max_score
            # Используем update_fields чтобы избежать рекурсии
            super().save(update_fields=['max_score'])

    
    def __str__(self):
        """Строковое представление теста: название"""
        return self.title
    
    class Meta:
        verbose_name = 'Тест'
        verbose_name_plural = 'Тесты'
        ordering = ['-id']  # Сортировка по id в обратном порядке (новые тесты сверху)

def validate_deadline(value):
    """
    Функция валидации для проверки, что срок выполнения не в прошлом.
    Используется в поле deadline модели TestAssignment.
    """
    if value and value < timezone.now():
        raise ValidationError("Срок выполнения не может быть в прошлом!")

class TestAssignment(models.Model):
    """
    Модель назначения теста группе студентов.
    Позволяет учителю назначить тест конкретной группе с дедлайном.
    """
    test = models.ForeignKey(
        Test, 
        on_delete=models.CASCADE, 
        related_name='assignments',
        verbose_name="Тест"
    )
    group = models.ForeignKey(
        StudyGroup, 
        on_delete=models.CASCADE, 
        related_name='assigned_tests',
        verbose_name="Группа"
    )
    assigned_at = models.DateTimeField(
        auto_now_add=True,  # Автоматически заполняется при создании
        verbose_name="Дата назначения"
    )
    deadline = models.DateTimeField(
        null=True, 
        blank=True,  # Дедлайн может отсутствовать
        validators=[validate_deadline],  # Проверка, что дедлайн не в прошлом
        verbose_name="Срок выполнения"
    )
    
    class Meta:
        unique_together = ('test', 'group')  # Тест может быть назначен группе только один раз
        ordering = ['-assigned_at']  # Сортировка по дате назначения (новые сверху)
        verbose_name = 'Назначение теста'
        verbose_name_plural = 'Назначения тестов'
        indexes = [
            models.Index(fields=['assigned_at']),  # Индексы для оптимизации запросов
            models.Index(fields=['deadline']),
        ]
    
    def __str__(self):
        """Строковое представление: тест для группы"""
        return f"Тест '{self.test.title}' для группы '{self.group.name}'"

class Question(models.Model):
    """
    Модель вопроса в тесте.
    Поддерживает разные типы вопросов: с одним вариантом ответа,
    с несколькими вариантами или с текстовым ответом.
    """
    QUESTION_TYPES = (
        ('single', 'Один вариант'),
        ('multiple', 'Несколько вариантов'),
        ('text', 'Текстовый ответ'),
    )
    test = models.ForeignKey(
        Test, 
        on_delete=models.CASCADE, 
        related_name='questions',
        verbose_name="Тест"
    )
    text = models.TextField(verbose_name="Текст вопроса")
    question_type = models.CharField(
        max_length=10, 
        choices=QUESTION_TYPES, 
        default='single',  # По умолчанию - вопрос с одним вариантом ответа
        verbose_name="Тип вопроса"
    )
    order = models.PositiveIntegerField(
        default=0,  # Порядок отображения вопроса в тесте
        verbose_name="Порядок отображения"
    )

    def save(self, *args, **kwargs):
        if self.order == 0:
            last_order = Question.objects.filter(test=self.test).aggregate(Max('order'))['order__max']
            self.order = (last_order or 0) + 1
        super().save(*args, **kwargs)

    def get_correct_answers(self):
        """Возвращает правильные ответы для вопроса"""
        if self.question_type == 'text':
            return None
        return self.answer_options.filter(is_correct=True)
    
    def get_absolute_url(self):
        return reverse('test-detail', kwargs={'pk': self.test.pk})
    
    def __str__(self):
        """Строковое представление: начало текста вопроса"""
        return f"Вопрос: {self.text[:50]}..."
    
    class Meta:
        verbose_name = 'Вопрос'
        verbose_name_plural = 'Вопросы'
        ordering = ['test', 'order']  # Сортировка по тесту, затем по порядку
        indexes = [
            models.Index(fields=['test', 'question_type']),  # Индекс для оптимизации запросов
        ]

class AnswerOption(models.Model):
    question = models.ForeignKey(
        Question, 
        on_delete=models.CASCADE, 
        related_name='answer_options',
        verbose_name="Вопрос"
    )
    text = models.CharField(
        max_length=200,
        verbose_name="Текст ответа"
    )
    is_correct = models.BooleanField(
        default=False,
        verbose_name="Правильный ответ"
    )

    def clean(self):
        """Перенесем валидацию в clean метод"""
        if not hasattr(self, 'question'):
            return  # Пропускаем если вопрос еще не установлен
            
        if self.is_correct and self.question.question_type == 'single':
            existing = AnswerOption.objects.filter(
                question=self.question, 
                is_correct=True
            ).exclude(pk=self.pk).exists()
            
            if existing:
                raise ValidationError("Для вопроса с одним вариантом ответа может быть только один правильный ответ")

    def __str__(self):
        return f"{self.text} ({'Правильный' if self.is_correct else 'Неправильный'})"
    
    def __str__(self):
        """Строковое представление: текст ответа и его правильность"""
        return f"{self.text} ({'Правильный' if self.is_correct else 'Неправильный'})"
    
    class Meta:
        verbose_name = 'Вариант ответа'
        verbose_name_plural = 'Варианты ответов'
        ordering = ['question', 'id']  # Сортировка по вопросу, затем по id

class TestResult(models.Model):
    """
    Модель результата прохождения теста студентом.
    Содержит общую информацию о результате: студент, тест, набранные баллы, дата.
    """
    STATUS_CHOICES = (
        ('completed', 'Завершено'),
        ('needs_review', 'Требует проверки'),
        ('in_progress', 'В процессе'),
    )
    status = models.CharField(
        max_length=12,
        choices=STATUS_CHOICES,
        default='in_progress',
        verbose_name="Статус"
    )
    student = models.ForeignKey(
        User, 
        on_delete=models.CASCADE,
        limit_choices_to={'role': 'student'},  # Только студенты могут иметь результаты
        related_name='test_results',
        verbose_name="Студент"
    )
    test = models.ForeignKey(
        Test, 
        on_delete=models.CASCADE, 
        related_name='results',
        verbose_name="Тест"
    )
    score = models.IntegerField(verbose_name="Набранные баллы")
    completed_at = models.DateTimeField(
        auto_now_add=True,  # Автоматически заполняется при создании
        verbose_name="Дата завершения"
    )

    # Метод для пересчета баллов
    def recalculate_score(self):
        total = 0
        for answer in self.answers.select_related('question').prefetch_related('selected_options'):
            if answer.question.question_type == 'text':
                # Для текстовых вопросов используем уже установленный балл
                if answer.score is not None:  # Если балл уже был установлен
                    total += answer.score
                # Если балл не установлен, не добавляем ничего
            else:
                correct = set(answer.question.answer_options.filter(is_correct=True))
                selected = set(answer.selected_options.all())
                if correct == selected:
                    total += 1
        self.score = total
        self.save()

    
    def __str__(self):
        """Строковое представление: результат студента по тесту"""
        return f"Результат {self.student.get_full_name()} по тесту '{self.test.title}': {self.score}"
    
    class Meta:
        verbose_name = 'Результат теста'
        verbose_name_plural = 'Результаты тестов'
        ordering = ['-completed_at']  # Сортировка по дате завершения (новые сверху)
        indexes = [
            models.Index(fields=['student', 'test']),  # Индексы для оптимизации запросов
            models.Index(fields=['completed_at']),
        ]

class StudentAnswer(models.Model):
    """
    Модель ответа студента на конкретный вопрос.
    Связана с результатом теста и содержит либо текстовый ответ,
    либо выбранные варианты ответов (в зависимости от типа вопроса).
    """
    result = models.ForeignKey(
        TestResult, 
        on_delete=models.CASCADE, 
        related_name='answers',
        verbose_name="Результат теста"
    )
    question = models.ForeignKey(
        Question, 
        on_delete=models.CASCADE, 
        related_name='student_answers',
        verbose_name="Вопрос"
    )
    answer_text = models.TextField(
        null=True, 
        blank=True,  # Может не быть текстового ответа
        verbose_name="Текстовый ответ"
    )
    selected_options = models.ManyToManyField(
        AnswerOption, 
        blank=True, 
        related_name='student_selections',
        verbose_name="Выбранные варианты"
    )
    score = models.IntegerField(
        default=0,
        verbose_name="Баллы за ответ"
    )

    def is_correct(self):
        """Проверяет, правильный ли ответ"""
        if self.question.question_type == 'text':
            return None  # Текстовые ответы требуют проверки учителем
        
        correct_options = set(self.question.get_correct_answers())
        selected_options = set(self.selected_options.all())
        return correct_options == selected_options
    
    def __str__(self):
        return f"Ответ на вопрос {self.question.id} в результате {self.result.id}"
    
    class Meta:
        verbose_name = 'Ответ студента'
        verbose_name_plural = 'Ответы студентов'
        unique_together = ('result', 'question')
        indexes = [
            models.Index(fields=['result', 'question']),
        ]

class TestStartTime(models.Model):
    student = models.ForeignKey(User, on_delete=models.CASCADE)
    assignment = models.ForeignKey(TestAssignment, on_delete=models.CASCADE)
    start_time = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ('student', 'assignment')
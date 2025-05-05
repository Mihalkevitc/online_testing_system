from django import forms
from django.contrib.auth import authenticate
from django.contrib.auth.forms import UserCreationForm
from .models import User
from .models import AnswerOption

class CustomUserCreationForm(UserCreationForm):
    first_name = forms.CharField(
        label='Имя',
        max_length=30,
        required=True,
        widget=forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Введите ваше имя'})
    )
    last_name = forms.CharField(
        label='Фамилия',
        max_length=30,
        required=True,
        widget=forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Введите вашу фамилию'})
    )
    email = forms.EmailField(
        label='Email',
        widget=forms.EmailInput(attrs={'class': 'form-control', 'placeholder': 'Введите ваш email'})
    )

    class Meta:
        model = User
        fields = ('email', 'first_name', 'last_name', 'password1', 'password2')
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['password1'].widget.attrs.update({'class': 'form-control', 'placeholder': 'Придумайте пароль'})
        self.fields['password2'].widget.attrs.update({'class': 'form-control', 'placeholder': 'Подтвердите пароль'})
    
    def save(self, commit=True):
        user = super().save(commit=False)
        user.role = 'student'  # Все новые пользователи - студенты
        if commit:
            user.save()
        return user

class CustomAuthenticationForm(forms.Form):
    email = forms.EmailField(
        label="Email",
        widget=forms.EmailInput(attrs={'class': 'form-control', 'placeholder': 'Введите ваш email'})
    )
    password = forms.CharField(
        label="Пароль",
        widget=forms.PasswordInput(attrs={'class': 'form-control', 'placeholder': 'Введите пароль'})
    )

    def clean(self):
        cleaned_data = super().clean()
        email = cleaned_data.get("email")
        password = cleaned_data.get("password")

        if email and password:
            user = authenticate(email=email, password=password)
            if user is None:
                raise forms.ValidationError("Неверный email или пароль")
            self.user = user

class UserProfileForm(forms.ModelForm):
    first_name = forms.CharField(
        label="Имя",
        required=True,
        widget=forms.TextInput(attrs={'class': 'form-control'})
    )
    last_name = forms.CharField(
        label="Фамилия",
        required=True,
        widget=forms.TextInput(attrs={'class': 'form-control'})
    )
    
    class Meta:
        model = User
        fields = ['email', 'first_name', 'last_name']
    
    def clean(self):
        cleaned_data = super().clean()
        first_name = cleaned_data.get('first_name', '').strip()
        last_name = cleaned_data.get('last_name', '').strip()
        
        if not first_name and not last_name:
            raise forms.ValidationError("Хотя бы одно из полей (Имя или Фамилия) должно быть заполнено")
        
        return cleaned_data
    

from django import forms
from .models import Question

class AnswerForm(forms.Form):
    def __init__(self, *args, **kwargs):
        questions = kwargs.pop('questions', None)  # Безопасное извлечение
        if questions is None:
            raise ValueError("Не переданы вопросы для теста")
        super().__init__(*args, **kwargs)
        
        for question in questions:
            field_name = f"question_{question.id}"
            if question.question_type == 'text':
                self.fields[field_name] = forms.CharField(
                    label=question.text,
                    widget=forms.Textarea,
                    required=False
                )
            else:
                choices = [(opt.id, opt.text) for opt in question.answer_options.all()]
                if question.question_type == 'single':
                    self.fields[field_name] = forms.ChoiceField(
                        label=question.text,
                        choices=choices,
                        widget=forms.RadioSelect,
                        required=False
                    )
                else:
                    self.fields[field_name] = forms.MultipleChoiceField(
                        label=question.text,
                        choices=choices,
                        widget=forms.CheckboxSelectMultiple,
                        required=False
                    )

class AnswerOptionForm(forms.ModelForm):
    class Meta:
        model = AnswerOption
        fields = ['text', 'is_correct']
        widgets = {
            'text': forms.Textarea(attrs={'rows': 3}),
            'is_correct': forms.CheckboxInput()
        }

    def __init__(self, *args, **kwargs):
        self.question = kwargs.pop('question', None)
        super().__init__(*args, **kwargs)
        
        # Для текстовых вопросов скрываем поле is_correct
        if self.question and self.question.question_type == 'text':
            self.fields['is_correct'].widget = forms.HiddenInput()
            self.fields['is_correct'].initial = False
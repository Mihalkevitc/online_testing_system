from django.db.models.signals import post_save, post_delete
from django.dispatch import receiver
from .models import Question, Test

@receiver([post_save, post_delete], sender=Question)
def update_test_max_score(sender, instance, **kwargs):
    """
    Обновляет максимальный балл теста при изменении вопросов
    """
    test = instance.test
    new_max_score = test.questions.count()  # Все вопросы дают по 1 баллу
    if test.max_score != new_max_score:
        test.max_score = new_max_score
        test.save(update_fields=['max_score'])
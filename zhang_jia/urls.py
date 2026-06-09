from django.urls import path
from . import views

app_name = 'zhang_jia'

urlpatterns = [
    path('memory/', views.memory, name='memory'),
    path('api/update-memory-score/', views.update_memory_score, name='update_memory_score'),
    path('api/get-memory-score/', views.get_memory_score, name='get_memory_score'),
]
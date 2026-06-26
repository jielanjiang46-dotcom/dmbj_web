from django.urls import path
from . import views

app_name = 'yucun'

urlpatterns = [
    path('xilaimian/', views.xilaimian, name='xilaimian'),
]
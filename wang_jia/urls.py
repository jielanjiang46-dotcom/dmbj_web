from django.urls import path
from . import views

app_name = 'wang_jia'

urlpatterns = [
    path('wang-trial/', views.wang_trial_view, name='wang_trial'),
    path('gutongjing/', views.gutongjing, name='gutongjing'),
]
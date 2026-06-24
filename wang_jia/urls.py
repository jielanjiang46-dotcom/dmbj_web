from django.urls import path
from . import views

app_name = 'wang_jia'

urlpatterns = [
    path('wang-trial/', views.wang_trial_view, name='wang_trial'),
    path('gutongjing/', views.gutongjing, name='gutongjing'),
    path('minesweeper/', views.minesweeper_page, name='minesweeper'),
    path('api/minesweeper/', views.api_minesweeper_action, name='api_minesweeper_action'),
    path('api/get-minesweeper-score/', views.api_get_minesweeper_score, name='api_get_minesweeper_score'),
]
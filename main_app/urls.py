"""定义 main_app的 URL 模式"""

from django.urls import path

from . import views

app_name = 'main_app'
urlpatterns = [
   # 主页
   path('', views.index, name='index'),
   path('nav/', views.navigation, name='navigation'),
   path('topics/',views.topics,name='topics'),

   # 特定主题的详细页面
    path('topics/<int:topic_id>/', views.topic, name='topic'),

    path('new_topic/', views.new_topic, name='new_topic'),
    path('new_entry/<int:topic_id>/', views.new_entry, name='new_entry'),
    path('edit_entry/<int:entry_id>/', views.edit_entry, name='edit_entry'),
]
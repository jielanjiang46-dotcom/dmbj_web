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
    path('add_comment/<int:entry_id>/', views.add_comment, name='add_comment'),
    path('entry/<int:entry_id>/like/', views.like_entry, name='like_entry'),
    path('comment/<int:comment_id>/delete/', views.delete_comment, name='delete_comment'),
    path('comment/<int:comment_id>/edit/', views.edit_comment, name='edit_comment'),
    path('delete_entry/<int:entry_id>/', views.delete_entry, name='delete_entry'),
    path('profile/<str:username>/', views.user_profile, name='user_profile'),
    path('users/edit/', views.edit_profile, name='edit_profile'),
    path('api/friend/add/', views.add_friend, name='add_friend'),
    path('api/user/search/', views.search_user, name='search_user'),
    path('accept_friend/', views.accept_friend, name='accept_friend'),
    path('reject_friend/', views.reject_friend, name='reject_friend'),
    path('cancel_request/', views.cancel_friend_request, name='cancel_request'),
    path('remove_friend/', views.remove_friend, name='remove_friend'),
    path('api/send_message/', views.send_message_api, name='send_message_api'),
    path('api/get_messages/', views.get_messages_api, name='get_messages_api'),
]
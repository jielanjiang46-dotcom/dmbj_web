from django.urls import path

from . import views

app_name = 'nanbudangan'

urlpatterns = [
    path('', views.index, name='index'),
    path('graybox/', views.graybox, name='graybox'),
    path('model/nanan_ship.glb', views.ship_model, name='ship_model'),
    path('model/nanan_interiors.glb', views.interiors_model, name='interiors_model'),
    path('model/nanan_people.glb', views.people_model, name='people_model'),
    path('model/nanan_first_person_arms.glb', views.first_person_arms_model, name='first_person_arms_model'),
    path('vendor/three.module.js', views.three_module, name='three_module'),
    path('scene/<str:scene_name>.png', views.scene_image, name='scene_image'),
]

from pathlib import Path

from django.http import FileResponse, Http404
from django.shortcuts import render


def index(request):
    return render(request, 'nanbudangan/index.html')


def graybox(request):
    return render(request, 'nanbudangan/graybox.html')


def ship_model(request):
    model_path = Path(__file__).resolve().parent / 'static' / 'nanbudangan' / 'models' / 'nanan_ship.glb'
    if not model_path.is_file():
        raise Http404('南安号模型不存在')
    return FileResponse(model_path.open('rb'), content_type='model/gltf-binary')


def interiors_model(request):
    model_path = Path(__file__).resolve().parent / 'static' / 'nanbudangan' / 'models' / 'nanan_interiors.glb'
    if not model_path.is_file():
        raise Http404('南安号内部模型不存在')
    return FileResponse(model_path.open('rb'), content_type='model/gltf-binary')


def people_model(request):
    model_path = Path(__file__).resolve().parent / 'static' / 'nanbudangan' / 'models' / 'nanan_people.glb'
    if not model_path.is_file():
        raise Http404('南安号人物模型不存在')
    return FileResponse(model_path.open('rb'), content_type='model/gltf-binary')


def first_person_arms_model(request):
    model_path = Path(__file__).resolve().parent / 'static' / 'nanbudangan' / 'models' / 'nanan_first_person_arms.glb'
    if not model_path.is_file():
        raise Http404('张海盐第一人称手臂模型不存在')
    return FileResponse(model_path.open('rb'), content_type='model/gltf-binary')


def three_module(request):
    module_path = Path(__file__).resolve().parent / 'static' / 'nanbudangan' / 'vendor' / 'three.module.js'
    if not module_path.is_file():
        raise Http404('Three.js 模块不存在')
    return FileResponse(module_path.open('rb'), content_type='text/javascript')


def scene_image(request, scene_name):
    filenames = {
        'ship': 'harbor_ship_v1.png',
        'farewell': 'harbor_farewell_v1.png',
        'gangway': 'gangway_party_v1.png',
        'waiting': 'first_class_waiting_v1.png',
        'crowd-a': 'queue_crowd_a_v1.png',
        'crowd-b': 'queue_crowd_b_v1.png',
    }
    filename = filenames.get(scene_name)
    if filename is None:
        raise Http404('场景画面不存在')
    image_path = Path(__file__).resolve().parent / 'static' / 'nanbudangan' / 'images' / filename
    if not image_path.is_file():
        raise Http404('场景画面不存在')
    return FileResponse(image_path.open('rb'), content_type='image/png')

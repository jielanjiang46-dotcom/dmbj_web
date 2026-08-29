from django.test import TestCase
from django.urls import reverse


class NanbudanganViewTests(TestCase):
    def test_graybox_page_is_available(self):
        response = self.client.get(reverse('nanbudangan:graybox'))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, '开场灰盒')
        self.assertContains(response, '一次点击招手')

    def test_index_page_is_available(self):
        response = self.client.get(reverse('nanbudangan:index'))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, '南部档案')
        self.assertContains(response, reverse('nanbudangan:ship_model'))
        self.assertContains(response, reverse('nanbudangan:interiors_model'))
        self.assertContains(response, reverse('nanbudangan:people_model'))
        self.assertContains(response, reverse('nanbudangan:first_person_arms_model'))
        self.assertContains(response, reverse('nanbudangan:graybox'))
        self.assertContains(response, '回头看看岸边')
        self.assertContains(response, '努力招手')
        self.assertContains(response, '点击一种舱位')
        self.assertContains(response, '首要嫌疑：船医')
        self.assertContains(response, '距离开船：三天')

    def test_ship_model_is_served_as_glb(self):
        response = self.client.get(reverse('nanbudangan:ship_model'))

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response['Content-Type'], 'model/gltf-binary')
        self.assertEqual(b''.join(response.streaming_content)[:4], b'glTF')

    def test_interiors_model_is_served_as_glb(self):
        response = self.client.get(reverse('nanbudangan:interiors_model'))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response['Content-Type'], 'model/gltf-binary')
        self.assertEqual(b''.join(response.streaming_content)[:4], b'glTF')

    def test_character_models_are_served_as_glb(self):
        for route in ('people_model', 'first_person_arms_model'):
            response = self.client.get(reverse(f'nanbudangan:{route}'))
            self.assertEqual(response.status_code, 200)
            self.assertEqual(response['Content-Type'], 'model/gltf-binary')
            self.assertEqual(b''.join(response.streaming_content)[:4], b'glTF')

    def test_three_module_is_served_locally(self):
        response = self.client.get(reverse('nanbudangan:three_module'))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response['Content-Type'], 'text/javascript')
        self.assertIn(b'WebGLRenderer', b''.join(response.streaming_content))

    def test_cinematic_scene_images_are_available(self):
        for scene_name in ('ship', 'farewell', 'gangway', 'waiting', 'crowd-a', 'crowd-b'):
            response = self.client.get(reverse('nanbudangan:scene_image', args=[scene_name]))
            self.assertEqual(response.status_code, 200)
            self.assertEqual(response['Content-Type'], 'image/png')

    def test_unknown_scene_image_returns_404(self):
        response = self.client.get(reverse('nanbudangan:scene_image', args=['unknown']))
        self.assertEqual(response.status_code, 404)

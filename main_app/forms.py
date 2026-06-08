from django import forms
from django.core.exceptions import ValidationError  # 【新增】导入异常类
from .models import Topic, Entry

class TopicForm(forms.ModelForm):
    class Meta:
        model = Topic
        fields = ['text']
        labels = {'text': ''}

class EntryForm(forms.ModelForm):
    class Meta:
        model = Entry
        fields = ['text', 'image']
        labels = {'text': ''}
        widgets = {
            'text': forms.Textarea(attrs={
                'cols': 80,
                'rows': 10,
                'placeholder': '写点什么，或者发张图...',
                # 注意：这里不需要 required=False，我们在 clean 中处理
                # 如果保留 required=False，必须配合下面的 clean 方法使用
            }),
            'image': forms.ClearableFileInput(attrs={
                'class': 'form-control-file',
                'accept': 'image/*'
            })
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # 允许 text 字段在单独校验时为空，以便我们进行自定义的联合校验
        self.fields['text'].required = False
        # 同时也允许 image 字段单独校验时为空（除非你强制必须传文件对象）
        # 通常 FileField 默认就是 required=True，如果没传文件会报错，
        # 所以建议把 image 也设为 False，统一在 clean 里判断
        self.fields['image'].required = False

    # 【关键修改】增加自定义校验逻辑
    def clean(self):
        cleaned_data = super().clean()
        text = cleaned_data.get("text")
        image = cleaned_data.get("image")

        # 逻辑：如果 text 为空（或全是空格） 且 image 也为空，则报错
        # strip() 用于防止用户只输入了几个空格也被当成有效内容
        if not text or not text.strip():
            if not image:
                raise ValidationError("内容不能为空！请输入文字或上传一张图片。")

        return cleaned_data
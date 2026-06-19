from django import forms
from django.contrib.auth.models import User
from django.contrib.auth.forms import UserCreationForm
from .models import UserProfile


class RegisterForm(UserCreationForm):
    """用户注册表单"""
    username = forms.CharField(
        label='用户名',
        min_length=3,
        max_length=20,
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': '请输入用户名（3-20位）',
        }),
        error_messages={
            'required': '请输入用户名',
            'min_length': '用户名至少3位',
            'unique': '该用户名已被注册',
        }
    )
    email = forms.EmailField(
        label='邮箱',
        required=True,
        widget=forms.EmailInput(attrs={
            'class': 'form-control',
            'placeholder': '请输入邮箱地址',
        })
    )
    password1 = forms.CharField(
        label='密码',
        widget=forms.PasswordInput(attrs={
            'class': 'form-control',
            'placeholder': '请输入密码（至少6位）',
        })
    )
    password2 = forms.CharField(
        label='确认密码',
        widget=forms.PasswordInput(attrs={
            'class': 'form-control',
            'placeholder': '请再次输入密码',
        })
    )
    nickname = forms.CharField(
        label='昵称',
        max_length=50,
        required=False,
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': '请输入昵称（选填）',
        })
    )

    class Meta:
        model = User
        fields = ['username', 'email', 'password1', 'password2', 'nickname']

    def save(self, commit=True):
        user = super().save(commit=False)
        user.email = self.cleaned_data['email']
        if commit:
            user.save()
            UserProfile.objects.create(
                user=user,
                nickname=self.cleaned_data.get('nickname', ''),
            )
        return user


class LoginForm(forms.Form):
    """用户登录表单"""
    username = forms.CharField(
        label='用户名',
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': '请输入用户名',
        })
    )
    password = forms.CharField(
        label='密码',
        widget=forms.PasswordInput(attrs={
            'class': 'form-control',
            'placeholder': '请输入密码',
        })
    )


class ProfileForm(forms.ModelForm):
    """个人信息修改表单"""
    email = forms.EmailField(
        label='邮箱',
        required=True,
        widget=forms.EmailInput(attrs={'class': 'form-control'})
    )

    class Meta:
        model = UserProfile
        fields = ['nickname', 'phone', 'avatar', 'bio']
        widgets = {
            'nickname': forms.TextInput(attrs={'class': 'form-control', 'placeholder': '请输入昵称'}),
            'phone': forms.TextInput(attrs={'class': 'form-control', 'placeholder': '请输入手机号'}),
            'avatar': forms.FileInput(attrs={'class': 'form-control'}),
            'bio': forms.Textarea(attrs={'class': 'form-control', 'rows': 3, 'placeholder': '介绍一下自己...'}),
        }
        labels = {
            'nickname': '昵称',
            'phone': '手机号',
            'avatar': '头像',
            'bio': '个人简介',
        }

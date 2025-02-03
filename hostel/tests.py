from django.core.exceptions import ValidationError
from django.test import TestCase
from django.contrib.auth import get_user_model
from django.core.files.uploadedfile import SimpleUploadedFile

User = get_user_model()

class UserRegistrationTest(TestCase):
    def test_register_owner(self):
        # Avatar giả để test
        avatar = SimpleUploadedFile(
            name="test_avatar.jpg",
            content=b"fake_image_content",
            content_type="image/jpeg"
        )

        # Tạo tài khoản chủ trọ
        user = User.objects.create_user(
            username="owner_user",
            password="securepassword123",
            email="owner@example.com",
            avatar=avatar,
            role=User.ROLE_OWNER,
        )

        # Kiểm tra các trường
        self.assertEqual(user.username, "owner_user")
        self.assertEqual(user.email, "owner@example.com")
        self.assertEqual(user.role, User.ROLE_OWNER)
        self.assertIsNotNone(user.avatar)
        self.assertIsNotNone(user.registration_date)

    def test_register_tenant(self):
        # Avatar giả để test
        avatar = SimpleUploadedFile(
            name="test_avatar.jpg",
            content=b"fake_image_content",
            content_type="image/jpeg"
        )

        # Tạo tài khoản người thuê
        user = User.objects.create_user(
            username="tenant_user",
            password="securepassword123",
            email="tenant@example.com",
            avatar=avatar,
            role=User.ROLE_TENANT,
        )

        # Kiểm tra các trường
        self.assertEqual(user.username, "tenant_user")
        self.assertEqual(user.email, "tenant@example.com")
        self.assertEqual(user.role, User.ROLE_TENANT)
        self.assertIsNotNone(user.avatar)
        self.assertIsNotNone(user.registration_date)

    def test_registration_without_avatar(self):
        # Đăng ký không có avatar
        with self.assertRaises(ValidationError):
            user = User(
                username="no_avatar_user",
                email="no_avatar@example.com",
                role=User.ROLE_TENANT,
            )
            user.clean()  # Gọi clean để kiểm tra validation
            user.save()  # Chỉ save nếu không có lỗi

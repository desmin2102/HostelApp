from rest_framework import serializers
from taggit.models import Tag
from taggit.serializers import TagListSerializerField
from .models import *
from .utils import get_coordinates_from_address


#xử lý user
class UserSerializer(serializers.ModelSerializer):
    phone_number = serializers.CharField(required=False, allow_blank=True)
    upload_avatar = serializers.ImageField(write_only=True, required=False)
    avatar = serializers.SerializerMethodField()

    def get_avatar(self, User):
        request = self.context.get('request')
        if User.avatar:
            request = self.context.get('request')
            if request:
                return request.build_absolute_uri('/static/%s' % User.avatar.name)
            return '/static/%s' % User.avatar.name

    class Meta:
        model = User
        fields = ['id', 'username', 'password', 'email', 'first_name', 'last_name', 'avatar', 'upload_avatar', 'role', 'phone_number']
        extra_kwargs = {
            'password': {'write_only': True},
        }

    def validate(self, data):
        # Kiểm tra số điện thoại không trùng lặp và có 10 chữ số
        phone_number = data.get('phone_number')

        if phone_number:
            if len(phone_number) != 10 or not phone_number.isdigit():
                raise serializers.ValidationError({"phone_number": "Số điện thoại phải có 10 chữ số"})
            if User.objects.filter(phone_number=phone_number).exists():
                raise serializers.ValidationError({"phone_number": "Số điện thoại đã tồn tài"})

        return data

    def create(self, validated_data):
        avatar_data = validated_data.pop('upload_avatar', None)
        user = User.objects.create_user(**validated_data)
        if avatar_data:
            user.avatar = avatar_data

        user.set_password(validated_data['password'])
        user.save()

        return user

    def update(self, instance, validated_data):
        # Lấy dữ liệu avatar mới nếu có
        avatar_data = validated_data.pop('upload_avatar', None)

        # Chỉ cho phép thay đổi những trường này, bao gồm cả upload_avatar
        allowed_fields = ['upload_avatar', 'avatar', 'password', 'first_name', 'last_name', 'email']

        # Cập nhật các trường trong `allowed_fields`
        for attr, value in validated_data.items():
            if attr in allowed_fields:
                setattr(instance, attr, value)

        # Nếu có tệp ảnh mới, cập nhật avatar
        if avatar_data:
            instance.avatar = avatar_data  # Cập nhật đường dẫn ảnh vào trường `avatar`

        # Nếu password được thay đổi, cần phải set lại password
        if 'password' in validated_data:
            instance.set_password(validated_data['password'])

        instance.save()

        return instance


#hình ảnh
class ImageSerializer(serializers.ModelSerializer):
    image = serializers.SerializerMethodField()

    def get_image(self, Image):
        request = self.context.get('request')
        if Image.image:
            request = self.context.get('request')
            if request:
                return request.build_absolute_uri('/static/%s' % Image.image.name )
            return '/static/%s' % Image.image.name
        return None

    class Meta:
        model = Image
        fields = ['id', 'image']  # Trả về chỉ trường 'image' đã được xử lý


#tag của taggit
class TagSerializer(serializers.ModelSerializer):
    class Meta:
        model = Tag
        fields = ['id', 'name']

#bài đăng cho thuê
class RentalPostSerializer(serializers.ModelSerializer):
    tags = TagListSerializerField()  # Giữ nguyên dạng list của tags
    images = ImageSerializer(many=True, read_only=True)
    uploaded_images = serializers.ListField(
        child=serializers.ImageField(allow_empty_file=False, use_url=False),
        write_only=True
    )
    owner = serializers.HiddenField(default=serializers.CurrentUserDefault())
    category = serializers.PrimaryKeyRelatedField(queryset=Category.objects.all())

    # Thêm các trường địa chỉ vào RentalPostSerializer
    city = serializers.PrimaryKeyRelatedField(queryset=City.objects.all())
    district = serializers.PrimaryKeyRelatedField(queryset=District.objects.all())
    ward = serializers.PrimaryKeyRelatedField(queryset=Ward.objects.all())
    address = serializers.CharField()

    class Meta:
        model = RentalPost
        fields = '__all__'
        read_only_fields = ['is_approved', 'active']

    def validate_uploaded_images(self, value):

        if len(value) < 3:
            raise serializers.ValidationError("Bạn cần tải lên ít nhất 3 ảnh.")
        return value

    def create(self, validated_data):
        uploaded_images = validated_data.pop("uploaded_images")
        city = validated_data.pop('city')
        district = validated_data.pop('district')
        ward = validated_data.pop('ward')
        address = validated_data.pop('address')
        tags = validated_data.pop('tags', [])

        # Kiểm tra xem đã có bài đăng khác ở địa chỉ này chưa
        existing_posts = RentalPost.objects.exclude(owner=validated_data['owner']).filter(
            city=city, district=district, ward=ward, address=address
        )

        if existing_posts.exists():
            raise serializers.ValidationError({"error": "Chủ sở hữu khác đã có bài đăng tại địa chỉ này."})

        # Tạo bài đăng mới và gán thông tin địa chỉ
        rental_post = RentalPost.objects.create(
            city=city,
            district=district,
            ward=ward,
            address=address,
            **validated_data
        )

        # Gán tags vào RentalPost
        tag_objects = [Tag.objects.get_or_create(name=tag)[0] for tag in tags]
        rental_post.tags.set(tag_objects)

        # Tạo các image liên quan đến bài đăng
        for image in uploaded_images:
            Image.objects.create(rental_post=rental_post, image=image)

        # Cập nhật tọa độ
        latitude, longitude = get_coordinates_from_address(address, city, district, ward)
        rental_post.latitude = latitude
        rental_post.longitude = longitude

        rental_post.save()

        return rental_post

    def update(self, instance, validated_data):
        # Lấy dữ liệu mới
        uploaded_images = validated_data.pop("uploaded_images", [])
        city = validated_data.pop('city', None)
        district = validated_data.pop('district', None)
        ward = validated_data.pop('ward', None)
        address = validated_data.pop('address', None)
        tags = validated_data.pop('tags', [])

        # Nếu có thay đổi địa chỉ, kiểm tra xem đã có bài đăng khác ở địa chỉ này chưa
        if address or city or district or ward:
            existing_posts = RentalPost.objects.exclude(owner=instance.owner).filter(
                city=city or instance.city,
                district=district or instance.district,
                ward=ward or instance.ward,
                address=address or instance.address
            )

            if existing_posts.exists():
                raise serializers.ValidationError({"error": "Chủ sở hữu khác đã có bài đăng tại địa chỉ này."})

            # Cập nhật lại tọa độ nếu có thay đổi địa chỉ
            if address and city and district and ward:
                latitude, longitude = get_coordinates_from_address(address, city, district, ward)
                instance.latitude = latitude
                instance.longitude = longitude

            # Cập nhật lại thông tin địa chỉ
            if address:
                instance.address = address
            if city:
                instance.city = city
            if district:
                instance.district = district
            if ward:
                instance.ward = ward

        # Cập nhật tags nếu có thay đổi
        if tags:
            tag_objects = [Tag.objects.get_or_create(name=tag)[0] for tag in tags]
            instance.tags.set(tag_objects)

        # Cập nhật các thông tin còn lại
        for attr, value in validated_data.items():
            setattr(instance, attr, value)

        # Lưu lại bản cập nhật
        instance.save()

        # Nếu có tải lên ảnh mới, xử lý chúng
        if uploaded_images:
            for image in uploaded_images:
                Image.objects.create(rental_post=instance, image=image)

        return instance


#bài đăng tìm chỗ ở
class TenantRequestSerializer(serializers.ModelSerializer):
    tenant = serializers.HiddenField(default=serializers.CurrentUserDefault())
    tags = TagListSerializerField()  # Giữ nguyên dạng list của tags
    city = serializers.PrimaryKeyRelatedField(queryset=City.objects.all())
    districts = serializers.PrimaryKeyRelatedField(many=True, queryset=District.objects.all(), required=False)
    wards = serializers.PrimaryKeyRelatedField(many=True, queryset=Ward.objects.all(), required=False)

    class Meta:
        model = TenantRequest
        fields = '__all__'
        read_only_fields = ['active']


    def create(self, validated_data):
        tags = validated_data.pop('tags', [])
        tenant_request = super().create(validated_data)
        tag_objects = [Tag.objects.get_or_create(name=tag)[0] for tag in tags]
        tenant_request.tags.set(tag_objects)
        tenant_request.save()
        return tenant_request

    def update(self, instance, validated_data):
        # Cập nhật các trường trong validated_data cho instance
        tags = validated_data.pop('tags', [])
        districts = validated_data.pop('districts', [])
        wards = validated_data.pop('wards', [])

        # Cập nhật các trường chính
        for attr, value in validated_data.items():
            setattr(instance, attr, value)

        # Cập nhật tags
        if tags is not None:
            tag_objects = [Tag.objects.get_or_create(name=tag)[0] for tag in tags]
            instance.tags.set(tag_objects)

        # Cập nhật districts và wards (nếu có)
        if districts is not None:
            instance.districts.set(districts)  # Cập nhật districts mới

        if wards is not None:
            instance.wards.set(wards)  # Cập nhật wards mới

        instance.save()  # Lưu lại các thay đổi
        return instance


#danh mục
class CategorySerializer(serializers.ModelSerializer):
    class Meta:
        model = Category
        fields = ['id', 'name']


class CitySerializer(serializers.ModelSerializer):
    class Meta:
        model = City
        fields = ['id', 'name']

class WardSerializer(serializers.ModelSerializer):
    name_with_district = serializers.SerializerMethodField()

    class Meta:
        model = Ward
        fields = ['id', 'name_with_district', 'district']

    def get_name_with_district(self, obj):
        return f"{obj.name} - {obj.district.name}"


class DistrictSerializer(serializers.ModelSerializer):
    class Meta:
        model = District
        fields = ['city','id', 'name']


class CommentSerializer(serializers.ModelSerializer):
    user_comment = UserSerializer(read_only=True)  # Đối tượng người dùng đầy đủ, chỉ đọc
    parent_comment = serializers.PrimaryKeyRelatedField(queryset=Comment.objects.all(), required=False)
    content_object = serializers.SerializerMethodField()

    class Meta:
        model = Comment
        fields = ['id', 'user_comment', 'content', 'parent_comment', 'content_object', 'created_at', 'updated_at']

    def get_content_object(self, obj):
        if obj.content_type:
            model_class = obj.content_type.model_class()  # Lấy lớp mô hình thực tế từ content_type
            content_object = model_class.objects.get(id=obj.object_id)  # Lấy đối tượng theo ID
            return {
                'type': obj.content_type.model,  # Loại mô hình: RentalPost hoặc TenantRequest
                'id': content_object.id,         # ID của đối tượng thực tế
            }
        return None


class LikeSerializer(serializers.ModelSerializer):
    user_like = UserSerializer(read_only=True)  # Đối tượng người dùng đầy đủ, chỉ đọc

    class Meta:
        model = Like
        fields = ['id', 'user_like', 'content_type', 'object_id', 'created_at']

class FollowSerializer(serializers.ModelSerializer):
    tenant = serializers.HiddenField(default=serializers.CurrentUserDefault())
    owner = serializers.PrimaryKeyRelatedField(queryset=User.objects.filter(role=User.UserRole.OWNER))

    class Meta:
        model = Follow
        fields = ['id','tenant', 'owner']


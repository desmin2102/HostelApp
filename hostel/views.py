from django.db.models import Count, Avg
from django.db.models.functions import TruncMonth, TruncQuarter, TruncYear
from oauth2_provider.contrib.rest_framework import permissions
from rest_framework import status, permissions, generics
from django.core.mail import send_mail
from django.conf import settings
from rest_framework import viewsets
from rest_framework.decorators import action
from rest_framework.exceptions import PermissionDenied, AuthenticationFailed
from rest_framework.permissions import  IsAuthenticated
from rest_framework.response import Response
from rest_framework.parsers import MultiPartParser, FormParser
from .models import *
from .perms import  IsStaffUser, IsRentalPostOwner, IsTenantRequestOwner
from .serializers import UserSerializer, RentalPostSerializer, TenantRequestSerializer, \
    ImageSerializer, CitySerializer, DistrictSerializer, WardSerializer, CommentSerializer, FollowSerializer
from . import serializers

class CityViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = City.objects.all()
    serializer_class = CitySerializer
class DistrictViewSet(viewsets.ReadOnlyModelViewSet):
    serializer_class = DistrictSerializer
    queryset = District.objects.all()

    def get_queryset(self):
        city_id = self.request.GET.get('city')
        if city_id:
            return District.objects.filter(city_id=city_id)
        return District.objects.all()

class WardViewSet(viewsets.ReadOnlyModelViewSet):
    serializer_class = WardSerializer
    queryset = Ward.objects.all()

    def get_queryset(self):
        district_ids = self.request.GET.getlist('district')
        if district_ids:
            return Ward.objects.filter(district_id__in=district_ids)
        return Ward.objects.all()

class ImageViewSet(viewsets.ModelViewSet):
    queryset = Image.objects.all()
    serializer_class = ImageSerializer

class BaseFilterViewSet(viewsets.ModelViewSet):
    permission_classes = [IsAuthenticated]

    def apply_filters(self, queryset):
        # Lọc theo thành phố nếu có
        city_id = self.request.GET.get('city')
        if city_id:
            queryset = queryset.filter(city_id=city_id)

        # Lọc theo nhiều quận nếu có
        district_ids = self.request.GET.getlist('district')
        if district_ids:
            queryset = queryset.filter(district__id__in=district_ids)

            # Lọc theo nhiều phường nếu có
            ward_ids = self.request.GET.getlist('ward')
            if ward_ids:
                queryset = queryset.filter(ward__id__in=ward_ids, ward__district__id__in=district_ids)

        # Lọc theo danh mục (category) nếu có
        category_id = self.request.GET.get('category')
        if category_id:
            queryset = queryset.filter(category_id=category_id)

        # Lọc theo tags nếu có
        tags = self.request.GET.get('tags')
        if tags:
            tags_list = tags.split(',')
            queryset = queryset.filter(tags__name__in=tags_list).distinct()

        # Lọc theo giá (price) nếu có
        min_price = self.request.GET.get('min_price')
        max_price = self.request.GET.get('max_price')

        # Nếu có min_price và max_price thì lọc theo
        if min_price is not None and max_price is not None:
            min_price = int(min_price)
            max_price = int(max_price)

            # Nếu là RentalPost, lọc theo price
            if hasattr(queryset.model, 'price'):
                queryset = queryset.filter(price__gte=min_price, price__lte=max_price)

            # Nếu là TenantRequest, lọc theo min_price và max_price
            if hasattr(queryset.model, 'min_price') and hasattr(queryset.model, 'max_price'):
                queryset = queryset.filter(
                    max_price__gte=min_price, min_price__lte=max_price
                )

        return queryset

    def get_queryset(self):
        queryset = self.queryset
        return self.apply_filters(queryset)

class RentalPostViewSet(BaseFilterViewSet):
    queryset = RentalPost.objects.all()
    serializer_class = RentalPostSerializer
    parser_class = [MultiPartParser, FormParser]

    def get_permissions(self):
        if self.action in ['create', 'update', 'partial_update', 'destroy']:
            return [IsAuthenticated(), IsRentalPostOwner()]
        return [permissions.AllowAny()]

    def get_queryset(self):

        queryset = super().get_queryset()
        if self.request.user.is_staff:
            return queryset
        return queryset.filter(is_approved=True)

    def perform_update(self, serializer):
        instance = self.get_object()
        if instance.owner != self.request.user:
            raise PermissionDenied("Bạn không có quyền cập nhật bài này.")

        serializer.save()

    def perform_create(self, serializer):
        user = self.request.user

        if not isinstance(user, User):
            raise PermissionDenied("Người dùng không hợp lệ.")

        if user.role != User.UserRole.OWNER:
            raise PermissionDenied("Chỉ Owner mới có thể tạo yêu cầu thuê nhà.")

        serializer.save(owner=user)

    def perform_destroy(self, instance):
        if instance.owner != self.request.user:
            raise PermissionDenied("Bạn không có quyền xóa bài này.")
        instance.delete()

    @action(detail=True, methods=['post'], permission_classes=[IsStaffUser])
    def approve(self, request, pk=None):
        rental_post = self.get_object()
        # Duyệt bài đăng
        rental_post.is_approved = True
        rental_post.save()
        # Lấy tất cả các tenant theo dõi chủ nhà
        tenants_following_owner = Follow.objects.filter(owner=rental_post.owner).values_list('tenant', flat=True)
        tenants = User.objects.filter(id__in=tenants_following_owner, role=User.UserRole.TENANT)
        # Gửi email cho các tenant
        subject = f"Bài đăng nhà mới: {rental_post.title}"
        message = f"Chủ nhà {rental_post.owner.username} mà bạn theo dõi vừa đăng bài mới."
        for tenant in tenants:
            send_mail(subject, message, settings.EMAIL_HOST_USER, [tenant.email])
        return Response({'status': 'Bài đăng đã được duyệt và email đã được gửi'}, status=status.HTTP_200_OK)


    @action(detail=True, methods=['post'], permission_classes=[IsStaffUser])
    def reject(self, request, pk=None):
        rental_post= self.get_object()
        rental_post.is_approved = False
        rental_post.save()
        return Response({'status': 'Bài đăng đã bị từ chối'}, status=status.HTTP_200_OK)

    @action(detail=True, methods=['post'], url_path='add_comment',permission_classes=[IsAuthenticated])
    def add_comment(self, request, pk=None):
        if not request.user.is_authenticated:
            raise AuthenticationFailed("Bạn hãy đăng nhập để sử dụng chức năng này.")
        rental_post = self.get_object()  # Lấy đối tượng RentalPost
        content_type = ContentType.objects.get_for_model(RentalPost)  # Lấy ContentType cho TenantRequest
        serializer = CommentSerializer(data=request.data)

        if serializer.is_valid():
            # Thêm comment vào đúng TenantRequest
            serializer.save(user=request.user, content_type=content_type, object_id=rental_post.id)
            return Response(serializer.data, status=status.HTTP_201_CREATED)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    @action(detail=True, methods=['delete'], url_path='delete_comment', permission_classes=[IsAuthenticated])
    def delete_comment(self, request, pk=None):
        rental_post = self.get_object()
        comment_id = request.data.get('comment_id')
        comment = Comment.objects.filter(id=comment_id, user=request.user,
                                         content_type=ContentType.objects.get_for_model(RentalPost),
                                         object_id=rental_post.id).first()

        if comment:
            comment.delete()
            return Response({"detail": "Đã xóa bình luận thành công."}, status=status.HTTP_200_OK)
        return Response({"detail": "Bình luận không tồn tại hoặc bạn không có quyền xóa bình luận này."},
                        status=status.HTTP_400_BAD_REQUEST)

    @action(detail=True, methods=['get'], url_path='get_comments')
    def get_comments(self, request, pk=None):
        rental_post = self.get_object()  # Lấy đối tượng TenantRequest
        comments = Comment.objects.filter(content_type=ContentType.objects.get_for_model(RentalPost),
                                          object_id=rental_post.id, parent_comment=None, active=True)
        serializer = CommentSerializer(comments, many=True)
        return Response(serializer.data)

    @action(detail=True, methods=['post'], url_path='add_like',permission_classes=[IsAuthenticated])
    def add_like(self, request, pk=None):
        if not request.user.is_authenticated:
            raise AuthenticationFailed("Bạn hãy đăng nhập để sử dụng chức năng này.")
        rental_post = self.get_object()  # Lấy đối tượng TenantRequest
        content_type = ContentType.objects.get_for_model(RentalPost)  # Lấy ContentType cho TenantRequest

        # Kiểm tra xem người dùng đã like bài đăng chưa
        existing_like = Like.objects.filter(user=request.user, content_type=content_type,
                                            object_id=rental_post.id).first()
        if existing_like:
            return Response({"detail": "Bạn đã thích bài đăng này rồi."}, status=status.HTTP_400_BAD_REQUEST)

        # Nếu chưa, tạo mới Like
        Like.objects.create(user=request.user, content_type=content_type, object_id=rental_post.id)
        return Response({"detail": "Đã thích bài đăng thành công."}, status=status.HTTP_201_CREATED)

    @action(detail=True, methods=['delete'], url_path='delete_like', permission_classes=[IsAuthenticated])
    def delete_like(self, request, pk=None):
        rental_post = self.get_object()
        like = Like.objects.filter(user=request.user, content_type=ContentType.objects.get_for_model(RentalPost),
                                   object_id=rental_post.id).first()

        if like:
            like.delete()
            return Response({"detail": "Đã xóa lượt thích thành công."}, status=status.HTTP_200_OK)
        return Response({"detail": "Lượt thích không tồn tại hoặc bạn không có quyền xóa lượt thích này."},
                        status=status.HTTP_400_BAD_REQUEST)

    @action(detail=True, methods=['get'], url_path='get_likes')
    def get_likes(self, request, pk=None):
        rental_post = self.get_object()  # Lấy đối tượng TenantRequest
        content_type = ContentType.objects.get_for_model(RentalPost)  # Lấy ContentType cho TenantRequest

        # Lấy danh sách likes
        likes = Like.objects.filter(content_type=content_type, object_id=rental_post.id)
        like_count = likes.count()
        return Response({"likes_count": like_count}, status=status.HTTP_200_OK)
class TenantRequestViewSet(BaseFilterViewSet):
    queryset = TenantRequest.objects.all()
    serializer_class = TenantRequestSerializer

    def get_permissions(self):
        if self.action in ['create', 'update', 'partial_update', 'destroy']:
            return [IsAuthenticated(), IsTenantRequestOwner()]
        return [permissions.AllowAny()]

    def get_queryset(self):
        return super().get_queryset()

    def perform_update(self, serializer):
        instance = self.get_object()
        if instance.tenant != self.request.user:
            raise PermissionDenied("Bạn không có quyền cập nhật bài này.")
        serializer.save()

    def perform_create(self, serializer):
        user = self.request.user
        if not isinstance(user, User):
            raise PermissionDenied("Người dùng không hợp lệ.")

        if user.role != User.UserRole.TENANT:
            raise PermissionDenied("Chỉ Tenant mới có thể tạo yêu cầu thuê nhà.")

        serializer.save(tenant=user)

    def perform_destroy(self, instance):
        if instance.tenant != self.request.user:
            raise PermissionDenied("Bạn không có quyền xóa bài này.")
        instance.delete()

    @action(detail=True, methods=['post'], url_path='add_comment',permission_classes=[IsAuthenticated])
    def add_comment(self, request, pk=None):
        if not request.user.is_authenticated:
            raise AuthenticationFailed("Bạn hãy đăng nhập để sử dụng chức năng này.")
        tenant_request = self.get_object()  # Lấy đối tượng TenantRequest
        content_type = ContentType.objects.get_for_model(TenantRequest)  # Lấy ContentType cho TenantRequest
        serializer = CommentSerializer(data=request.data)

        if serializer.is_valid():
            # Thêm comment vào đúng TenantRequest
            serializer.save(user=request.user, content_type=content_type, object_id=tenant_request.id)
            return Response(serializer.data, status=status.HTTP_201_CREATED)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    @action(detail=True, methods=['delete'], url_path='delete_comment', permission_classes=[IsAuthenticated])
    def delete_comment(self, request, pk=None):
        tenant_request = self.get_object()
        comment_id = request.data.get('comment_id')
        comment = Comment.objects.filter(id=comment_id, user=request.user,
                                         content_type=ContentType.objects.get_for_model(TenantRequest),
                                         object_id=tenant_request.id).first()

        if comment:
            comment.delete()
            return Response({"detail": "Đã xóa bình luận thành công."}, status=status.HTTP_200_OK)
        return Response({"detail": "Bình luận không tồn tại hoặc bạn không có quyền xóa bình luận này."},
                        status=status.HTTP_400_BAD_REQUEST)

    @action(detail=True, methods=['get'], url_path='get_comments')
    def get_comments(self, request, pk=None):
        tenant_request = self.get_object()  # Lấy đối tượng TenantRequest
        comments = Comment.objects.filter(content_type=ContentType.objects.get_for_model(TenantRequest),
                                          object_id=tenant_request.id, parent_comment=None, active=True)
        serializer = CommentSerializer(comments, many=True)
        return Response(serializer.data)

    @action(detail=True, methods=['post'], url_path='add_like',permission_classes=[IsAuthenticated])
    def add_like(self, request, pk=None):
        if not request.user.is_authenticated:
            raise AuthenticationFailed("Bạn hãy đăng nhập để sử dụng chức năng này.")
        tenant_request = self.get_object()  # Lấy đối tượng TenantRequest
        content_type = ContentType.objects.get_for_model(TenantRequest)  # Lấy ContentType cho TenantRequest

        # Kiểm tra xem người dùng đã like bài đăng chưa
        existing_like = Like.objects.filter(user=request.user, content_type=content_type,
                                            object_id=tenant_request.id).first()
        if existing_like:
            return Response({"detail": "Bạn đã thích bài đăng này rồi."}, status=status.HTTP_400_BAD_REQUEST)

        # Nếu chưa, tạo mới Like
        Like.objects.create(user=request.user, content_type=content_type, object_id=tenant_request.id)
        return Response({"detail": "Đã thích bài đăng thành công."}, status=status.HTTP_201_CREATED)

    @action(detail=True, methods=['delete'], url_path='delete_like', permission_classes=[IsAuthenticated])
    def delete_like(self, request, pk=None):
        tenant_request = self.get_object()
        like = Like.objects.filter(user=request.user, content_type=ContentType.objects.get_for_model(TenantRequest),
                                   object_id=tenant_request.id).first()

        if like:
            like.delete()
            return Response({"detail": "Đã xóa lượt thích thành công."}, status=status.HTTP_200_OK)
        return Response({"detail": "Lượt thích không tồn tại hoặc bạn không có quyền xóa lượt thích này."},
                        status=status.HTTP_400_BAD_REQUEST)

    @action(detail=True, methods=['get'], url_path='get_likes')
    def get_likes(self, request, pk=None):
        tenant_request = self.get_object()  # Lấy đối tượng TenantRequest
        content_type = ContentType.objects.get_for_model(TenantRequest)  # Lấy ContentType cho TenantRequest

        # Lấy danh sách likes
        likes = Like.objects.filter(content_type=content_type, object_id=tenant_request.id)
        like_count = likes.count()
        return Response({"likes_count": like_count}, status=status.HTTP_200_OK)


class UserViewSet(viewsets.GenericViewSet, generics.CreateAPIView, generics.UpdateAPIView,generics.ListAPIView):
    queryset = User.objects.filter(is_active=True)
    serializer_class = UserSerializer
    parser_classes = [MultiPartParser, ]


    def get_permissions(self):
        if self.action in ['get_current_user', 'partial_update']:
            return [permissions.IsAuthenticated()]
        return [permissions.AllowAny()]

    def update(self, request, *args, **kwargs):
        # Lấy user đang xác thực
        user = request.user

        # Kiểm tra nếu `pk` trong URL khớp với id của user đang xác thực
        if str(user.id) != str(kwargs.get('pk')):
            raise PermissionDenied("Bạn không có quyền thay đổi thông tin của người dùng này.")

        return super().update(request, *args, **kwargs)

    @action(methods=['get'], url_path='current-user', detail=False)
    def get_current_user(self, request):
        # Trả về thông tin của người dùng hiện tại
        return Response(UserSerializer(request.user).data)


class FollowViewSet(viewsets.ViewSet):
    queryset = Follow.objects.all()
    permission_classes = [IsAuthenticated]

    @action(detail=True, methods=['post'], url_path='follow')
    def follow(self, request, pk=None):
        tenant = request.user

        # Kiểm tra xem người dùng có phải là tenant không
        if tenant.role != User.UserRole.TENANT:
            return Response({"message": "chỉ có người tìm nhà mới có thể theo dõi"}, status=status.HTTP_400_BAD_REQUEST)
        try:
            owner = User.objects.get(id=pk, role=User.UserRole.OWNER)
        except User.DoesNotExist:
            return Response({"message": "Không tìm thấy chủ nhà với ID này."}, status=status.HTTP_404_NOT_FOUND)

        # Kiểm tra xem người thuê có theo dõi chủ nhà này chưa
        if Follow.objects.filter(tenant=tenant, owner=owner).exists():
            return Response({"message": "Bạn đã theo dõi chủ nhà này rồi"}, status=status.HTTP_400_BAD_REQUEST)

        # Tạo mối quan hệ follow
        follow = Follow.objects.create(tenant=tenant, owner=owner)
        return Response(FollowSerializer(follow).data, status=status.HTTP_201_CREATED)

    @action(detail=True, methods=['post'], url_path='unfollow')
    def unfollow(self, request, pk=None):
        tenant = request.user

        # Kiểm tra xem người dùng có phải là tenant không
        if tenant.role != User.UserRole.TENANT:
            return Response({"message": "Only tenants can unfollow owners."}, status=status.HTTP_400_BAD_REQUEST)

        owner = User.objects.get(id=pk, role=User.UserRole.OWNER)

        # Kiểm tra xem người thuê có theo dõi chủ nhà này hay không
        follow = Follow.objects.filter(tenant=tenant, owner=owner).first()
        if not follow:
            return Response({"message": "Not following this owner."}, status=status.HTTP_400_BAD_REQUEST)

        # Hủy theo dõi
        follow.delete()
        return Response({"message": "Successfully unfollowed."}, status=status.HTTP_204_NO_CONTENT)

class StatisticsViewSet(viewsets.ViewSet):
    permission_classes = [IsAuthenticated]

    @action(detail=False, methods=['get'])
    def user_statistics(self, request):
        self.permission_classes = [IsAuthenticated, IsStaffUser]

        period = request.GET.get('period', 'month')  # month, quarter, year
        year = request.GET.get('year', None)  # Lấy năm từ tham số 'year'

        filters = {}
        if year:
            filters['date_joined__year'] = year

        trunc_mapping = {
            'month': TruncMonth('date_joined'),
            'quarter': TruncQuarter('date_joined'),
            'year': TruncYear('date_joined'),
        }

        trunc_function = trunc_mapping.get(period, TruncMonth('date_joined'))  # Mặc định là TruncMonth

        # Lọc theo năm nếu có
        data = User.objects.filter(**filters).annotate(period=trunc_function).values('period').annotate(
            count=Count('id')).order_by('period')

        return Response(data)

    @action(detail=False, methods=['get'])
    def owner_statistics(self, request):
        self.permission_classes = [IsAuthenticated, IsStaffUser]

        period = request.GET.get('period', 'month')  # month, quarter, year, day
        year = request.GET.get('year', None)  # Lấy năm từ tham số 'year'
        owners = User.objects.filter(role=User.UserRole.OWNER)

        filters = {}
        if year:
            filters['date_joined__year'] = year

        trunc_mapping = {
            'month': TruncMonth('date_joined'),
            'quarter': TruncQuarter('date_joined'),
            'year': TruncYear('date_joined'),
        }

        trunc_function = trunc_mapping.get(period, TruncMonth('date_joined'))

        # Lọc theo năm nếu có
        data = owners.filter(**filters).annotate(period=trunc_function).values('period').annotate(
            count=Count('id')).order_by('period')

        return Response(data)

    @action(detail=False, methods=['get'])
    def average_price_by_city_and_district(self, request):
        city_id = request.GET.get('city')  # Lấy city từ tham số 'city'
        if not city_id:
            return Response({"error": "City ID is required"}, status=400)

        # Lọc các RentalPost theo city_id
        rental_posts = RentalPost.objects.filter(city_id=city_id,is_approved=True)

        # Nhóm theo quận và tính giá trung bình cho mỗi quận
        data = rental_posts.values('district') \
            .annotate(average_price=Avg('price')) \
            .order_by('district')

        # Ép kiểu phần giá trung bình thành số nguyên ngay trong truy vấn
        result = [
            {"district": item['district'], "average_price": int(item['average_price'])}
            for item in data
        ]

        return Response(result)
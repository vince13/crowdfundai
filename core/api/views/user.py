from rest_framework import viewsets, decorators, response, permissions
from ...models import User
from ..serializers import UserSerializer

class UserViewSet(viewsets.ModelViewSet):
    queryset = User.objects.all()
    serializer_class = UserSerializer
    permission_classes = [permissions.IsAuthenticated]

    @decorators.action(detail=False, methods=['get'])
    def profile(self, request):
        """Get the current user's profile"""
        serializer = self.get_serializer(request.user)
        return response.Response(serializer.data) 
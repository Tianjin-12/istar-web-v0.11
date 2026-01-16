from rest_framework import serializers
from .models import Mention_percentage

class Mention_percentageSerializer(serializers.ModelSerializer):
    class Meta:
        model = Mention_percentage
        fields = '__all__'

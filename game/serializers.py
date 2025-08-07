from rest_framework import serializers
from django.contrib.auth.models import User
from .models import (
    Question, DecoyQuestion, GameRoom, Player, 
    GameRound, PlayerAnswer, Vote, GameEvent
)


class UserSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = ['id', 'username', 'first_name', 'last_name']


class QuestionSerializer(serializers.ModelSerializer):
    class Meta:
        model = Question
        fields = ['id', 'text', 'category', 'difficulty', 'min_answer', 'max_answer']


class DecoyQuestionSerializer(serializers.ModelSerializer):
    class Meta:
        model = DecoyQuestion
        fields = ['id', 'text', 'min_answer', 'max_answer']


class PlayerSerializer(serializers.ModelSerializer):
    user = UserSerializer(read_only=True)
    
    class Meta:
        model = Player
        fields = ['id', 'user', 'nickname', 'score', 'is_connected', 'joined_at']


class GameRoomSerializer(serializers.ModelSerializer):
    host = UserSerializer(read_only=True)
    players = PlayerSerializer(many=True, read_only=True)
    player_count = serializers.ReadOnlyField()
    can_start = serializers.ReadOnlyField()
    
    class Meta:
        model = GameRoom
        fields = [
            'id', 'name', 'host', 'status', 'max_players', 
            'current_round', 'total_rounds', 'created_at', 
            'started_at', 'finished_at', 'players', 'player_count', 'can_start'
        ]


class GameRoomCreateSerializer(serializers.ModelSerializer):
    class Meta:
        model = GameRoom
        fields = ['name', 'max_players', 'total_rounds']


class PlayerAnswerSerializer(serializers.ModelSerializer):
    player = PlayerSerializer(read_only=True)
    
    class Meta:
        model = PlayerAnswer
        fields = ['id', 'player', 'answer', 'submitted_at']


class VoteSerializer(serializers.ModelSerializer):
    voter = PlayerSerializer(read_only=True)
    accused = PlayerSerializer(read_only=True)
    
    class Meta:
        model = Vote
        fields = ['id', 'voter', 'accused', 'submitted_at']


class GameRoundSerializer(serializers.ModelSerializer):
    question = QuestionSerializer(read_only=True)
    decoy_question = DecoyQuestionSerializer(read_only=True)
    imposter = PlayerSerializer(read_only=True)
    answers = PlayerAnswerSerializer(many=True, read_only=True)
    votes = VoteSerializer(many=True, read_only=True)
    
    class Meta:
        model = GameRound
        fields = [
            'id', 'round_number', 'question', 'decoy_question', 
            'imposter', 'status', 'started_at', 'discussion_started_at',
            'voting_started_at', 'finished_at', 'answers', 'votes'
        ]


class GameEventSerializer(serializers.ModelSerializer):
    player = PlayerSerializer(read_only=True)
    
    class Meta:
        model = GameEvent
        fields = ['id', 'event_type', 'player', 'data', 'timestamp']


class JoinRoomSerializer(serializers.Serializer):
    nickname = serializers.CharField(max_length=50)


class SubmitAnswerSerializer(serializers.Serializer):
    answer = serializers.IntegerField()


class SubmitVoteSerializer(serializers.Serializer):
    accused_player_id = serializers.IntegerField()

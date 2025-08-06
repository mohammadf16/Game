from rest_framework import serializers
from django.contrib.auth import authenticate
from .models import (
    User, Question, DecoyQuestion, GameRoom, Player, 
    GameRound, PlayerAnswer, Vote, GameEvent, PlayerGameStats,
    Leaderboard
)


class UserSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = [
            'id', 'username', 'email', 'first_name', 'last_name',
            'total_games', 'total_wins', 'total_score', 'win_rate',
            'total_imposter_wins', 'total_detective_wins',
            'imposter_success_rate', 'avatar', 'created_at', 'last_active'
        ]
        read_only_fields = [
            'total_games', 'total_wins', 'total_score', 'win_rate',
            'total_imposter_wins', 'total_detective_wins',
            'imposter_success_rate', 'created_at', 'last_active'
        ]


class UserRegistrationSerializer(serializers.ModelSerializer):
    password = serializers.CharField(write_only=True, min_length=6)
    password_confirm = serializers.CharField(write_only=True)
    
    class Meta:
        model = User
        fields = ['username', 'email', 'password', 'password_confirm', 'first_name', 'last_name']
    
    def validate(self, attrs):
        if attrs['password'] != attrs['password_confirm']:
            raise serializers.ValidationError("Passwords don't match")
        return attrs
    
    def create(self, validated_data):
        validated_data.pop('password_confirm')
        password = validated_data.pop('password')
        user = User.objects.create_user(password=password, **validated_data)
        return user


class UserLoginSerializer(serializers.Serializer):
    username = serializers.CharField()
    password = serializers.CharField()
    
    def validate(self, attrs):
        username = attrs.get('username')
        password = attrs.get('password')
        
        if username and password:
            user = authenticate(username=username, password=password)
            if not user:
                raise serializers.ValidationError('Invalid credentials')
            if not user.is_active:
                raise serializers.ValidationError('User account is disabled')
            attrs['user'] = user
        else:
            raise serializers.ValidationError('Must include username and password')
        
        return attrs


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
    is_online = serializers.SerializerMethodField()
    
    class Meta:
        model = Player
        fields = [
            'id', 'user', 'nickname', 'score', 'is_connected', 
            'joined_at', 'last_active', 'is_online'
        ]
    
    def get_is_online(self, obj):
        # Consider player online if active in last 5 minutes
        from django.utils import timezone
        from datetime import timedelta
        threshold = timezone.now() - timedelta(minutes=5)
        return obj.last_active > threshold


class GameRoomSerializer(serializers.ModelSerializer):
    host = UserSerializer(read_only=True)
    players = PlayerSerializer(many=True, read_only=True)
    player_count = serializers.ReadOnlyField()
    can_start = serializers.ReadOnlyField()
    can_user_join = serializers.SerializerMethodField()
    current_user_player = serializers.SerializerMethodField()
    
    class Meta:
        model = GameRoom
        fields = [
            'id', 'name', 'host', 'status', 'max_players', 
            'current_round', 'total_rounds', 'is_private', 'room_code',
            'created_at', 'started_at', 'finished_at', 'players', 
            'player_count', 'can_start', 'can_user_join', 'current_user_player'
        ]
    
    def get_can_user_join(self, obj):
        request = self.context.get('request')
        if request and request.user.is_authenticated:
            return obj.can_user_join(request.user)
        return False
    
    def get_current_user_player(self, obj):
        request = self.context.get('request')
        if request and request.user.is_authenticated:
            try:
                player = obj.players.get(user=request.user)
                return PlayerSerializer(player, context=self.context).data
            except Player.DoesNotExist:
                pass
        return None


class GameRoomCreateSerializer(serializers.ModelSerializer):
    class Meta:
        model = GameRoom
        fields = ['name', 'max_players', 'total_rounds', 'is_private']


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


class PlayerGameStatsSerializer(serializers.ModelSerializer):
    player = PlayerSerializer(read_only=True)
    room_name = serializers.CharField(source='room.name', read_only=True)
    
    class Meta:
        model = PlayerGameStats
        fields = [
            'id', 'player', 'room_name', 'round_number', 'role', 
            'result', 'points_earned', 'was_voted_out', 'correct_votes',
            'created_at'
        ]


class GameEventSerializer(serializers.ModelSerializer):
    player = PlayerSerializer(read_only=True)
    
    class Meta:
        model = GameEvent
        fields = ['id', 'event_type', 'player', 'data', 'timestamp']


class JoinRoomSerializer(serializers.Serializer):
    nickname = serializers.CharField(max_length=50)
    room_code = serializers.CharField(max_length=6, required=False)


class SubmitAnswerSerializer(serializers.Serializer):
    answer = serializers.IntegerField()


class SubmitVoteSerializer(serializers.Serializer):
    accused_player_id = serializers.IntegerField()


class UserStatsSerializer(serializers.Serializer):
    """Serializer for user statistics and game history"""
    user = UserSerializer(read_only=True)
    recent_games = serializers.SerializerMethodField()
    game_stats = serializers.SerializerMethodField()
    favorite_categories = serializers.SerializerMethodField()
    
    def get_recent_games(self, obj):
        recent_players = Player.objects.filter(
            user=obj
        ).select_related('room').order_by('-joined_at')[:10]
        
        games_data = []
        for player in recent_players:
            games_data.append({
                'room_id': str(player.room.id),
                'room_name': player.room.name,
                'status': player.room.status,
                'score': player.score,
                'joined_at': player.joined_at,
                'can_rejoin': player.room.can_user_join(obj)
            })
        return games_data
    
    def get_game_stats(self, obj):
        return {
            'total_games': obj.total_games,
            'total_wins': obj.total_wins,
            'total_score': obj.total_score,
            'win_rate': obj.win_rate,
            'imposter_wins': obj.total_imposter_wins,
            'detective_wins': obj.total_detective_wins,
            'imposter_success_rate': obj.imposter_success_rate
        }
    
    def get_favorite_categories(self, obj):
        # Get most played question categories
        from django.db.models import Count
        stats = PlayerGameStats.objects.filter(player__user=obj).values(
            'room__rounds__question__category'
        ).annotate(
            count=Count('id')
        ).order_by('-count')[:5]
        
        return [{'category': stat['room__rounds__question__category'], 
                'count': stat['count']} for stat in stats]


class LeaderboardSerializer(serializers.ModelSerializer):
    user = UserSerializer(read_only=True)
    
    class Meta:
        model = Leaderboard
        fields = [
            'user', 'period', 'total_games', 'total_wins', 
            'total_score', 'win_rate', 'imposter_wins', 
            'detective_wins', 'rank', 'updated_at'
        ]
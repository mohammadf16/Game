from django.db import models
from django.contrib.auth.models import AbstractUser
from django.utils import timezone
import uuid


class User(AbstractUser):
    """Extended user model with game statistics"""
    email = models.EmailField(unique=True)
    total_games = models.IntegerField(default=0)
    total_wins = models.IntegerField(default=0)
    total_imposter_wins = models.IntegerField(default=0)
    total_detective_wins = models.IntegerField(default=0)
    total_score = models.IntegerField(default=0)
    avatar = models.CharField(max_length=50, default='default')  # For avatar selection
    created_at = models.DateTimeField(auto_now_add=True)
    last_active = models.DateTimeField(auto_now=True)
    
    USERNAME_FIELD = 'username'
    REQUIRED_FIELDS = ['email']
    
    @property
    def win_rate(self):
        if self.total_games == 0:
            return 0
        return (self.total_wins / self.total_games) * 100
    
    @property
    def imposter_success_rate(self):
        imposter_games = PlayerGameStats.objects.filter(
            player__user=self, 
            role='imposter'
        ).count()
        if imposter_games == 0:
            return 0
        return (self.total_imposter_wins / imposter_games) * 100
    
    def __str__(self):
        return self.username


class Question(models.Model):
    """Questions for the Number Hunt game"""
    CATEGORY_CHOICES = [
        ('lifestyle', 'Lifestyle & Habits'),
        ('preferences', 'Preferences & Opinions'),
        ('experiences', 'Experiences'),
        ('hypothetical', 'Hypothetical'),
        ('general', 'General'),
    ]
    
    text = models.TextField(help_text="The main question text")
    category = models.CharField(max_length=20, choices=CATEGORY_CHOICES, default='general')
    min_answer = models.IntegerField(default=1, help_text="Minimum expected answer")
    max_answer = models.IntegerField(default=20, help_text="Maximum expected answer")
    difficulty = models.IntegerField(default=1, choices=[(1, 'Easy'), (2, 'Medium'), (3, 'Hard')])
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    
    def __str__(self):
        return f"{self.text[:50]}..."
    
    class Meta:
        ordering = ['category', 'difficulty']


class DecoyQuestion(models.Model):
    """Decoy questions for imposters"""
    text = models.TextField(help_text="The decoy question text")
    min_answer = models.IntegerField(default=1)
    max_answer = models.IntegerField(default=20)
    is_active = models.BooleanField(default=True)
    
    def __str__(self):
        return f"Decoy: {self.text[:30]}..."


class GameRoom(models.Model):
    """Game room where players gather"""
    STATUS_CHOICES = [
        ('waiting', 'Waiting for Players'),
        ('in_progress', 'Game in Progress'),
        ('finished', 'Game Finished'),
    ]
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField(max_length=100)
    host = models.ForeignKey(User, on_delete=models.CASCADE, related_name='hosted_games')
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='waiting')
    max_players = models.IntegerField(default=8)
    current_round = models.IntegerField(default=0)
    total_rounds = models.IntegerField(default=5)
    is_private = models.BooleanField(default=False)
    room_code = models.CharField(max_length=6, unique=True, blank=True, null=True)  # For private rooms
    created_at = models.DateTimeField(auto_now_add=True)
    started_at = models.DateTimeField(null=True, blank=True)
    finished_at = models.DateTimeField(null=True, blank=True)
    
    def generate_unique_room_code(self):
        """Generate a unique room code that doesn't already exist"""
        import random
        import string
        
        max_attempts = 100  # Prevent infinite loop
        for _ in range(max_attempts):
            code = ''.join(random.choices(string.ascii_uppercase + string.digits, k=6))
            if not GameRoom.objects.filter(room_code=code).exists():
                return code
        
        # If we can't find a unique code after max_attempts, use a longer code
        return ''.join(random.choices(string.ascii_uppercase + string.digits, k=8))
    
    def save(self, *args, **kwargs):
        if self.is_private and not self.room_code:
            self.room_code = self.generate_unique_room_code()
        super().save(*args, **kwargs)
    
    def __str__(self):
        return f"Room: {self.name} ({self.status})"
    
    @property
    def player_count(self):
        return self.players.count()
    
    def can_start(self):
        return self.player_count >= 3 and self.status == 'waiting'
    
    def can_user_join(self, user):
        """Check if a user can join this room"""
        if self.status == 'finished':
            return False
        
        # If user is already a player in this room, they can rejoin
        if self.players.filter(user=user).exists():
            return True
            
        # If game is in progress, no new players can join
        if self.status == 'in_progress':
            return False
            
        # If waiting and room not full, user can join
        return self.player_count < self.max_players


class Player(models.Model):
    """Player in a game room"""
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    room = models.ForeignKey(GameRoom, on_delete=models.CASCADE, related_name='players')
    nickname = models.CharField(max_length=50)
    score = models.IntegerField(default=0)
    is_connected = models.BooleanField(default=True)
    joined_at = models.DateTimeField(auto_now_add=True)
    last_active = models.DateTimeField(auto_now=True)
    
    class Meta:
        unique_together = ['user', 'room']
    
    def __str__(self):
        return f"{self.nickname} in {self.room.name}"
    
    def update_activity(self):
        """Update last active timestamp"""
        self.last_active = timezone.now()
        self.save(update_fields=['last_active'])


class GameRound(models.Model):
    """Individual round in a game"""
    STATUS_CHOICES = [
        ('setup', 'Setting Up'),
        ('answering', 'Players Answering'),
        ('discussion', 'Discussion Phase'),
        ('voting', 'Voting Phase'),
        ('results', 'Results Phase'),
        ('finished', 'Round Finished'),
    ]
    
    room = models.ForeignKey(GameRoom, on_delete=models.CASCADE, related_name='rounds')
    round_number = models.IntegerField()
    question = models.ForeignKey(Question, on_delete=models.CASCADE)
    decoy_question = models.ForeignKey(DecoyQuestion, on_delete=models.CASCADE)
    imposter = models.ForeignKey(Player, on_delete=models.CASCADE, related_name='imposter_rounds')
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='setup')
    started_at = models.DateTimeField(auto_now_add=True)
    discussion_started_at = models.DateTimeField(null=True, blank=True)
    voting_started_at = models.DateTimeField(null=True, blank=True)
    finished_at = models.DateTimeField(null=True, blank=True)
    
    class Meta:
        unique_together = ['room', 'round_number']
    
    def __str__(self):
        return f"Round {self.round_number} in {self.room.name}"


class PlayerAnswer(models.Model):
    """Player's answer in a round"""
    round = models.ForeignKey(GameRound, on_delete=models.CASCADE, related_name='answers')
    player = models.ForeignKey(Player, on_delete=models.CASCADE)
    answer = models.IntegerField()
    submitted_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        unique_together = ['round', 'player']
    
    def __str__(self):
        return f"{self.player.nickname}: {self.answer}"


class Vote(models.Model):
    """Player's vote for who they think is the imposter"""
    round = models.ForeignKey(GameRound, on_delete=models.CASCADE, related_name='votes')
    voter = models.ForeignKey(Player, on_delete=models.CASCADE, related_name='votes_cast')
    accused = models.ForeignKey(Player, on_delete=models.CASCADE, related_name='votes_received')
    submitted_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        unique_together = ['round', 'voter']
    
    def __str__(self):
        return f"{self.voter.nickname} votes {self.accused.nickname}"


class PlayerGameStats(models.Model):
    """Individual player statistics for each game"""
    ROLE_CHOICES = [
        ('detective', 'Detective'),
        ('imposter', 'Imposter'),
    ]
    
    RESULT_CHOICES = [
        ('win', 'Win'),
        ('loss', 'Loss'),
    ]
    
    player = models.ForeignKey(Player, on_delete=models.CASCADE, related_name='game_stats')
    room = models.ForeignKey(GameRoom, on_delete=models.CASCADE, related_name='player_stats')
    round_number = models.IntegerField()
    role = models.CharField(max_length=20, choices=ROLE_CHOICES)
    result = models.CharField(max_length=20, choices=RESULT_CHOICES)
    points_earned = models.IntegerField(default=0)
    was_voted_out = models.BooleanField(default=False)
    correct_votes = models.IntegerField(default=0)  # For detectives
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        unique_together = ['player', 'room', 'round_number']
    
    def __str__(self):
        return f"{self.player.nickname} - Round {self.round_number} - {self.role} - {self.result}"


class GameEvent(models.Model):
    """Events that happen during the game for logging/replay"""
    EVENT_TYPES = [
        ('player_joined', 'Player Joined'),
        ('player_left', 'Player Left'),
        ('player_reconnected', 'Player Reconnected'),
        ('game_started', 'Game Started'),
        ('round_started', 'Round Started'),
        ('answer_submitted', 'Answer Submitted'),
        ('discussion_started', 'Discussion Started'),
        ('voting_started', 'Voting Started'),
        ('vote_submitted', 'Vote Submitted'),
        ('round_ended', 'Round Ended'),
        ('game_ended', 'Game Ended'),
    ]
    
    room = models.ForeignKey(GameRoom, on_delete=models.CASCADE, related_name='events')
    event_type = models.CharField(max_length=20, choices=EVENT_TYPES)
    player = models.ForeignKey(Player, on_delete=models.CASCADE, null=True, blank=True)
    data = models.JSONField(default=dict, blank=True)
    timestamp = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        ordering = ['-timestamp']
    
    def __str__(self):
        return f"{self.event_type} in {self.room.name}"


class UserSession(models.Model):
    """Track user sessions for reconnection"""
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='sessions')
    session_key = models.CharField(max_length=100, unique=True)
    current_room = models.ForeignKey(GameRoom, on_delete=models.SET_NULL, null=True, blank=True)
    last_activity = models.DateTimeField(auto_now=True)
    created_at = models.DateTimeField(auto_now_add=True)
    
    def __str__(self):
        return f"Session for {self.user.username}"


class Leaderboard(models.Model):
    """Leaderboard entries for different time periods"""
    PERIOD_CHOICES = [
        ('daily', 'Daily'),
        ('weekly', 'Weekly'),
        ('monthly', 'Monthly'),
        ('all_time', 'All Time'),
    ]
    
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    period = models.CharField(max_length=20, choices=PERIOD_CHOICES)
    period_start = models.DateTimeField()
    period_end = models.DateTimeField()
    total_games = models.IntegerField(default=0)
    total_wins = models.IntegerField(default=0)
    total_score = models.IntegerField(default=0)
    imposter_games = models.IntegerField(default=0)
    imposter_wins = models.IntegerField(default=0)
    detective_games = models.IntegerField(default=0)
    detective_wins = models.IntegerField(default=0)
    rank = models.IntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        unique_together = ['user', 'period', 'period_start']
        ordering = ['-total_score', '-total_wins']
    
    @property
    def win_rate(self):
        if self.total_games == 0:
            return 0
        return (self.total_wins / self.total_games) * 100
    
    def __str__(self):
        return f"{self.user.username} - {self.period} - Rank {self.rank}"
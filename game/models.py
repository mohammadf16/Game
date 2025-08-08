from django.db import models
from django.contrib.auth.models import User
import uuid
from django.utils import timezone


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
    created_at = models.DateTimeField(auto_now_add=True)
    started_at = models.DateTimeField(null=True, blank=True)
    finished_at = models.DateTimeField(null=True, blank=True)
    
    def __str__(self):
        return f"Room: {self.name} ({self.status})"
    
    @property
    def player_count(self):
        return self.players.count()
    
    def can_start(self):
        return self.player_count >= 3 and self.status == 'waiting'


class Player(models.Model):
    """Player in a game room"""
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    room = models.ForeignKey(GameRoom, on_delete=models.CASCADE, related_name='players')
    nickname = models.CharField(max_length=50)
    score = models.IntegerField(default=0)
    is_connected = models.BooleanField(default=True)
    has_submitted_answer = models.BooleanField(default=False)
    has_voted = models.BooleanField(default=False)
    joined_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        unique_together = ['user', 'room']
    
    def __str__(self):
        return f"{self.nickname} in {self.room.name}"


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


class GameEvent(models.Model):
    """Events that happen during the game for logging/replay"""
    EVENT_TYPES = [
        ('player_joined', 'Player Joined'),
        ('player_left', 'Player Left'),
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

// Number Hunt Game JavaScript with Authentication
class NumberHuntGame {
    constructor() {
        this.currentUser = null;
        this.authToken = localStorage.getItem('authToken');
        this.currentRoom = null;
        this.currentRound = null;
        this.gameState = 'menu';
        this.pollInterval = null;
        
        this.initializeApp();
    }
    
    async initializeApp() {
        await this.checkAuthStatus();
        this.setupEventListeners();
        
        // Check for reconnection opportunities
        if (this.currentUser) {
            await this.checkReconnection();
        }
    }
    
    async checkAuthStatus() {
        if (this.authToken) {
            try {
                const user = await this.apiCall('/api/auth/profile/');
                this.currentUser = user.user;
                this.showDashboard();
            } catch (error) {
                // Token is invalid, remove it
                localStorage.removeItem('authToken');
                this.authToken = null;
                this.showAuthScreen();
            }
        } else {
            this.showAuthScreen();
        }
    }
    
    async checkReconnection() {
        try {
            const response = await this.apiCall('/api/auth/check-reconnection/');
            if (response.can_reconnect) {
                this.showReconnectNotification(response.room);
            }
        } catch (error) {
            console.log('No reconnection available');
        }
    }
    
    setupEventListeners() {
        // Auth form submissions
        document.getElementById('loginForm')?.addEventListener('submit', (e) => this.handleLogin(e));
        document.getElementById('registerForm')?.addEventListener('submit', (e) => this.handleRegister(e));
        
        // Menu buttons
        document.getElementById('createRoomBtn')?.addEventListener('click', () => this.showCreateRoom());
        document.getElementById('joinRoomBtn')?.addEventListener('click', () => this.showJoinRoom());
        document.getElementById('leaderboardBtn')?.addEventListener('click', () => this.showLeaderboard());
        document.getElementById('profileBtn')?.addEventListener('click', () => this.showProfile());
        document.getElementById('logoutBtn')?.addEventListener('click', () => this.handleLogout());
        
        // Game form submissions
        document.getElementById('createRoomForm')?.addEventListener('submit', (e) => this.handleCreateRoom(e));
        document.getElementById('joinRoomForm')?.addEventListener('submit', (e) => this.handleJoinRoom(e));
        document.getElementById('joinByCodeForm')?.addEventListener('submit', (e) => this.handleJoinByCode(e));
        document.getElementById('answerForm')?.addEventListener('submit', (e) => this.handleSubmitAnswer(e));
        
        // Game actions
        document.getElementById('startGameBtn')?.addEventListener('click', () => {
            this.startGame();
        });
        
        // Close room button
        document.getElementById('closeRoomBtn')?.addEventListener('click', () => {
            this.closeRoom();
        });
        
        document.getElementById('startVotingBtn')?.addEventListener('click', () => this.startVoting());
        document.getElementById('submitVoteBtn')?.addEventListener('click', () => this.submitVote());
        document.getElementById('continueBtn')?.addEventListener('click', () => this.continueToNextRound());
        
        // Navigation buttons
        document.querySelectorAll('.back-btn').forEach(btn => {
            btn.addEventListener('click', () => this.showDashboard());
        });
        
        // Auth toggle buttons
        document.getElementById('showRegisterBtn')?.addEventListener('click', () => this.showRegister());
        document.getElementById('showLoginBtn')?.addEventListener('click', () => this.showLogin());
    }
    
    // API Methods with Authentication
    async apiCall(endpoint, method = 'GET', data = null) {
        const url = endpoint;
        const options = {
            method,
            headers: {
                'Content-Type': 'application/json',
            }
        };
        
        // Add authorization header if token exists
        if (this.authToken) {
            options.headers['Authorization'] = `Token ${this.authToken}`;
        }
        
        if (data) {
            options.body = JSON.stringify(data);
        }
        
        try {
            const response = await fetch(url, options);
            const result = await response.json();
            
            if (!response.ok) {
                if (response.status === 401) {
                    // Unauthorized - token expired or invalid
                    this.handleAuthError();
                    throw new Error('Authentication required');
                }
                throw new Error(result.error || result.detail || 'API call failed');
            }
            
            return result;
        } catch (error) {
            this.showNotification(error.message, 'error');
            throw error;
        }
    }
    
    handleAuthError() {
        localStorage.removeItem('authToken');
        this.authToken = null;
        this.currentUser = null;
        this.showAuthScreen();
    }
    
    // Authentication Methods
    async handleLogin(e) {
        e.preventDefault();
        const formData = new FormData(e.target);
        
        try {
            const loginData = {
                username: formData.get('username'),
                password: formData.get('password')
            };
            
            const response = await this.apiCall('/api/auth/login/', 'POST', loginData);
            
            this.authToken = response.token;
            this.currentUser = response.user;
            localStorage.setItem('authToken', this.authToken);
            
            if (response.redirect_to_admin && response.user.is_staff) {
                window.location.href = '/admin-dashboard/';
            } else {
                this.showNotification('Login successful!', 'success');
                this.showDashboard();
            }
            
            // Check for reconnection after login
            await this.checkReconnection();
            
        } catch (error) {
            console.error('Login failed:', error);
        }
    }
    
    async handleRegister(e) {
        e.preventDefault();
        const formData = new FormData(e.target);
        
        try {
            const registerData = {
                username: formData.get('username'),
                email: formData.get('email'),
                password: formData.get('password'),
                password_confirm: formData.get('password_confirm'),
                first_name: formData.get('first_name') || '',
                last_name: formData.get('last_name') || ''
            };
            
            const response = await this.apiCall('/api/auth/register/', 'POST', registerData);
            
            this.authToken = response.token;
            this.currentUser = response.user;
            localStorage.setItem('authToken', this.authToken);
            
            this.showNotification('Registration successful!', 'success');
            this.showDashboard();
            
        } catch (error) {
            console.error('Registration failed:', error);
        }
    }
    
    async handleLogout() {
        try {
            await this.apiCall('/api/auth/logout/', 'POST');
        } catch (error) {
            console.log('Logout API call failed, but continuing with local logout');
        }
        
        localStorage.removeItem('authToken');
        this.authToken = null;
        this.currentUser = null;
        this.stopPolling();
        this.showAuthScreen();
        this.showNotification('Logged out successfully', 'success');
    }
    
    // UI Management
    showScreen(screenId) {
        document.querySelectorAll('.screen').forEach(screen => {
            screen.classList.add('hidden');
        });
        document.getElementById(screenId)?.classList.remove('hidden');
    }
    
    showAuthScreen() {
        this.gameState = 'auth';
        this.showScreen('authScreen');
        this.showLogin(); // Default to login form
    }
    
    showLogin() {
        document.getElementById('loginForm')?.classList.remove('hidden');
        document.getElementById('registerForm')?.classList.add('hidden');
        document.getElementById('authTitle').textContent = 'Login to Number Hunt';
    }
    
    showRegister() {
        document.getElementById('loginForm')?.classList.add('hidden');
        document.getElementById('registerForm')?.classList.remove('hidden');
        document.getElementById('authTitle').textContent = 'Create Account';
    }
    
    showDashboard() {
        this.gameState = 'dashboard';
        this.showScreen('dashboardScreen');
        this.loadDashboardData();
    }
    
    async loadDashboardData() {
        try {
            // Load user stats and recent games
            const userStats = await this.apiCall('/api/auth/profile/');
            this.updateDashboardUI(userStats);
            
            // Load user's rooms
            const userRooms = await this.apiCall('/api/rooms/user/');
            this.updateUserRooms(userRooms);
            
        } catch (error) {
            console.error('Failed to load dashboard data:', error);
        }
    }
    
    updateDashboardUI(userStats) {
        // Update user info
        document.getElementById('userWelcome').textContent = `Welcome, ${userStats.user.username}!`;
        document.getElementById('userTotalGames').textContent = userStats.user.total_games;
        document.getElementById('userTotalWins').textContent = userStats.user.total_wins;
        document.getElementById('userTotalScore').textContent = userStats.user.total_score;
        document.getElementById('userWinRate').textContent = `${userStats.user.win_rate.toFixed(1)}%`;
        
        // Update recent games
        const recentGamesContainer = document.getElementById('recentGames');
        recentGamesContainer.innerHTML = '';
        
        userStats.recent_games.forEach(game => {
            const gameCard = document.createElement('div');
            gameCard.className = 'game-card';
            gameCard.innerHTML = `
                <div class="game-info">
                    <h4>${game.room_name}</h4>
                    <p>Status: ${game.status}</p>
                    <p>Score: ${game.score}</p>
                    <p>Joined: ${new Date(game.joined_at).toLocaleDateString()}</p>
                </div>
                ${game.can_rejoin ? `
                    <button class="btn btn-primary" onclick="game.rejoinGame('${game.room_id}')">
                        ${game.status === 'in_progress' ? 'Rejoin' : 'View'}
                    </button>
                ` : ''}
            `;
            recentGamesContainer.appendChild(gameCard);
        });
    }
    
    updateUserRooms(userRooms) {
        // Update current room if exists
        if (userRooms.current_room) {
            const currentRoomContainer = document.getElementById('currentRoom');
            currentRoomContainer.innerHTML = `
                <div class="current-room-card">
                    <h3>${userRooms.current_room.name}</h3>
                    <p>Status: ${userRooms.current_room.status}</p>
                    <p>Players: ${userRooms.current_room.player_count}/${userRooms.current_room.max_players}</p>
                    <button class="btn btn-primary" onclick="game.rejoinGame('${userRooms.current_room.id}')">
                        ${userRooms.current_room.status === 'waiting' ? 'Join Lobby' : 'Rejoin Game'}
                    </button>
                </div>
            `;
        } else {
            document.getElementById('currentRoom').innerHTML = '<p>No active games</p>';
        }
    }
    
    async rejoinGame(roomId) {
        try {
            this.currentRoom = await this.apiCall(`/api/rooms/${roomId}/`);
            
            if (this.currentRoom.status === 'waiting') {
                this.showLobby();
            } else if (this.currentRoom.status === 'in_progress') {
                this.showGame();
            } else {
                this.showNotification('Game has finished', 'info');
            }
        } catch (error) {
            console.error('Failed to rejoin game:', error);
        }
    }
    
    showReconnectNotification(room) {
        const notification = document.createElement('div');
        notification.className = 'reconnect-notification';
        notification.innerHTML = `
            <div class="notification-content">
                <h3>Rejoin Game?</h3>
                <p>You have an active game: ${room.name}</p>
                <div class="notification-actions">
                    <button class="btn btn-primary" onclick="game.rejoinGame('${room.id}')">Rejoin</button>
                    <button class="btn btn-secondary" onclick="this.parentElement.parentElement.parentElement.remove()">Dismiss</button>
                </div>
            </div>
        `;
        document.body.appendChild(notification);
        
        // Auto-remove after 10 seconds
        setTimeout(() => {
            if (notification.parentNode) {
                notification.remove();
            }
        }, 10000);
    }
    
    showCreateRoom() {
        this.showScreen('createRoomScreen');
    }
    
    showJoinRoom() {
        this.showScreen('joinRoomScreen');
        this.loadAvailableRooms();
    }
    
    showProfile() {
        this.showScreen('profileScreen');
        this.loadProfileData();
    }
    
    async loadProfileData() {
        try {
            // Load detailed user stats
            const userStats = await this.apiCall('/api/auth/profile/');
            
            // Load game history
            const gameHistory = await this.apiCall('/api/stats/history/');
            
            this.updateProfileUI(userStats, gameHistory);
            
        } catch (error) {
            console.error('Failed to load profile data:', error);
        }
    }
    
    updateProfileUI(userStats, gameHistory) {
        // Update profile info
        document.getElementById('profileUsername').textContent = userStats.user.username;
        document.getElementById('profileEmail').textContent = userStats.user.email;
        document.getElementById('profileJoinDate').textContent = new Date(userStats.user.created_at).toLocaleDateString();
        
        // Update detailed stats
        document.getElementById('detailedTotalGames').textContent = userStats.game_stats.total_games;
        document.getElementById('detailedTotalWins').textContent = userStats.game_stats.total_wins;
        document.getElementById('detailedTotalScore').textContent = userStats.game_stats.total_score;
        document.getElementById('detailedWinRate').textContent = `${userStats.game_stats.win_rate.toFixed(1)}%`;
        document.getElementById('imposterWins').textContent = userStats.game_stats.imposter_wins;
        document.getElementById('detectiveWins').textContent = userStats.game_stats.detective_wins;
        document.getElementById('imposterSuccessRate').textContent = `${userStats.game_stats.imposter_success_rate.toFixed(1)}%`;
        
        // Update game history
        const historyContainer = document.getElementById('gameHistory');
        historyContainer.innerHTML = '';
        
        gameHistory.forEach(stat => {
            const historyItem = document.createElement('div');
            historyItem.className = 'history-item';
            historyItem.innerHTML = `
                <div class="history-info">
                    <h4>${stat.room_name}</h4>
                    <p>Round ${stat.round_number} - ${stat.role}</p>
                    <p>Result: ${stat.result} (${stat.points_earned} points)</p>
                    <p>Date: ${new Date(stat.created_at).toLocaleDateString()}</p>
                </div>
                <div class="history-result ${stat.result}">
                    ${stat.result === 'win' ? '✓' : '✗'}
                </div>
            `;
            historyContainer.appendChild(historyItem);
        });
    }
    
    showLeaderboard() {
        this.showScreen('leaderboardScreen');
        this.loadLeaderboard();
    }
    
    async loadLeaderboard() {
        try {
            const leaderboard = await this.apiCall('/api/leaderboard/?period=all_time&limit=50');
            this.updateLeaderboardUI(leaderboard);
            
        } catch (error) {
            console.error('Failed to load leaderboard:', error);
        }
    }
    
    updateLeaderboardUI(leaderboard) {
        const leaderboardContainer = document.getElementById('leaderboardList');
        leaderboardContainer.innerHTML = '';
        
        leaderboard.forEach(entry => {
            const entryElement = document.createElement('div');
            entryElement.className = `leaderboard-entry ${entry.user.username === this.currentUser.username ? 'current-user' : ''}`;
            entryElement.innerHTML = `
                <div class="rank">#${entry.rank}</div>
                <div class="user-info">
                    <h4>${entry.user.username}</h4>
                    <p>${entry.total_games} games played</p>
                </div>
                <div class="stats">
                    <div class="score">${entry.total_score} points</div>
                    <div class="win-rate">${entry.win_rate.toFixed(1)}% wins</div>
                </div>
            `;
            leaderboardContainer.appendChild(entryElement);
        });
    }
    
    showLobby() {
        this.gameState = 'lobby';
        this.showScreen('lobbyScreen');
        this.startPolling();
    }
    
    showGame() {
        this.gameState = 'playing';
        this.showScreen('gameScreen');
        this.startPolling();
    }
    
    // Room Management (Updated)
    async handleCreateRoom(e) {
        e.preventDefault();
        const formData = new FormData(e.target);
        
        try {
            const roomData = {
                name: formData.get('roomName'),
                max_players: parseInt(formData.get('maxPlayers')),
                total_rounds: parseInt(formData.get('totalRounds')),
                is_private: formData.get('isPrivate') === 'on',
                nickname: formData.get('nickname') || this.currentUser.username
            };
            
            this.currentRoom = await this.apiCall('/api/rooms/create/', 'POST', roomData);
        
        // Set current player info - creator is always the host
        if (this.currentRoom && this.currentRoom.players) {
            this.currentPlayer = this.currentRoom.players.find(player => 
                player.user_id === this.currentUser.id || player.is_host
            );
        }
        
        this.showNotification('Room created successfully!', 'success');
        this.showLobby();
        this.updateLobbyUI();
            
        } catch (error) {
            console.error('Failed to create room:', error);
        }
    }
    
    async handleJoinRoom(e) {
        e.preventDefault();
        const formData = new FormData(e.target);
        const roomId = formData.get('roomId');
        
        if (!roomId) {
            this.showNotification('Please select a room to join', 'warning');
            return;
        }
        
        try {
            const joinData = {
                nickname: formData.get('nickname') || this.currentUser.username
            };
            
            const response = await this.apiCall(`/api/rooms/${roomId}/join/`, 'POST', joinData);
            this.currentRoom = response.room;
            
            // Set current player info from the room data
            if (this.currentRoom && this.currentRoom.players) {
                this.currentPlayer = this.currentRoom.players.find(player => 
                    player.user_id === this.currentUser.id || player.nickname === joinData.nickname
                );
            }
            
            this.showNotification(response.message, 'success');
            
            if (this.currentRoom.status === 'waiting') {
                this.showLobby();
            } else {
                this.showGame();
            }
            
        } catch (error) {
            console.error('Failed to join room:', error);
        }
    }
    
    async handleJoinByCode(e) {
        e.preventDefault();
        const formData = new FormData(e.target);
        
        try {
            const joinData = {
                room_code: formData.get('roomCode').toUpperCase(),
                nickname: formData.get('nickname') || this.currentUser.username
            };
            
            const response = await this.apiCall('/api/rooms/join-by-code/', 'POST', joinData);
            this.currentRoom = response.room;
            
            this.showNotification(response.message, 'success');
            
            if (this.currentRoom.status === 'waiting') {
                this.showLobby();
            } else {
                this.showGame();
            }
            
        } catch (error) {
            console.error('Failed to join room by code:', error);
        }
    }
    
    async loadAvailableRooms() {
        try {
            const rooms = await this.apiCall('/api/rooms/');
            this.displayAvailableRooms(rooms);
        } catch (error) {
            console.error('Failed to load rooms:', error);
        }
    }
    
    displayAvailableRooms(rooms) {
        const container = document.getElementById('availableRooms');
        if (!container) return;
        
        container.innerHTML = '';
        
        if (rooms.length === 0) {
            container.innerHTML = '<p class="text-center">No rooms available. Create one!</p>';
            return;
        }
        
        rooms.forEach(room => {
            const roomCard = document.createElement('div');
            roomCard.className = 'room-card';
            roomCard.innerHTML = `
                <div class="room-header">
                    <h3 class="room-title">${room.name}</h3>
                    <span class="room-status ${room.status}">${room.status}</span>
                    ${room.is_private ? '<span class="private-badge">🔒 Private</span>' : ''}
                </div>
                <div class="room-info">
                    <p>Players: ${room.player_count}/${room.max_players}</p>
                    <p>Rounds: ${room.total_rounds}</p>
                    <p>Host: ${room.host.username}</p>
                    ${room.current_user_player ? '<p class="user-in-room">✓ You are in this room</p>' : ''}
                </div>
                <div class="room-actions">
                    <button class="btn btn-primary" onclick="game.selectRoom('${room.id}')" 
                            ${room.can_user_join ? '' : 'disabled'}>
                        ${room.current_user_player ? 'Rejoin' : 
                          !room.can_user_join ? 'Cannot Join' : 'Select'}
                    </button>
                </div>
            `;
            container.appendChild(roomCard);
        });
    }
    
    selectRoom(roomId) {
        document.getElementById('selectedRoomId').value = roomId;
        
        // Highlight selected room
        document.querySelectorAll('.room-card').forEach(card => {
            card.classList.remove('selected');
        });
        event.target.closest('.room-card').classList.add('selected');
    }
    
    // Game Flow (Updated to handle reconnection)
    async startPolling() {
        this.stopPolling();
        
        // Update activity when starting to poll
        if (this.currentRoom) {
            try {
                await this.apiCall(`/api/rooms/${this.currentRoom.id}/activity/`, 'POST');
            } catch (error) {
                console.log('Activity update failed');
            }
        }
        
        this.pollInterval = setInterval(() => {
            this.pollForUpdates();
        }, 2000);
    }
    
    async pollForUpdates() {
        try {
            if (!this.currentRoom) return;
            
            // Update activity
            await this.apiCall(`/api/rooms/${this.currentRoom.id}/activity/`, 'POST');
            
            if (this.gameState === 'lobby') {
                this.currentRoom = await this.apiCall(`/api/rooms/${this.currentRoom.id}/`);
                this.updateLobbyUI();
                
                if (this.currentRoom.status === 'in_progress') {
                    this.showGame();
                }
            } else if (this.gameState === 'playing') {
                this.currentRoom = await this.apiCall(`/api/rooms/${this.currentRoom.id}/`);
                this.currentRound = await this.apiCall(`/api/rooms/${this.currentRoom.id}/current-round/`);
                this.updateGameUI();
                
                if (this.currentRoom.status === 'finished') {
                    this.showResults();
                }
            }
        } catch (error) {
            if (error.message.includes('Authentication required')) {
                // Don't log auth errors during polling
                return;
            }
            console.error('Polling error:', error);
        }
    }
    
    // Continue with existing game methods but with authentication context...
    // [Rest of the game methods remain the same but with proper authentication handling]
    
    // Utility Methods
    showNotification(message, type = 'success') {
        const notification = document.createElement('div');
        notification.className = `notification ${type}`;
        notification.textContent = message;
        
        document.body.appendChild(notification);
        
        setTimeout(() => {
            notification.classList.add('show');
        }, 100);
        
        setTimeout(() => {
            notification.classList.remove('show');
            setTimeout(() => {
                if (notification.parentNode) {
                    notification.remove();
                }
            }, 300);
        }, 3000);
    }
    
    stopPolling() {
        if (this.pollInterval) {
            clearInterval(this.pollInterval);
            this.pollInterval = null;
        }
    }

    // Missing Lobby and Game Functions
    updateLobbyUI() {
        if (!this.currentRoom) return;
        
        const roomName = document.getElementById('roomName');
        const playerCount = document.getElementById('playerCount');
        const playersList = document.getElementById('playersList');
        const startGameBtn = document.getElementById('startGameBtn');
        const roomCodeDisplay = document.getElementById('roomCodeDisplay');
        const roomCode = document.getElementById('roomCode');
        const closeRoomBtn = document.getElementById('closeRoomBtn');
        
        if (roomName) roomName.textContent = this.currentRoom.name;
        if (playerCount) {
            const current = this.currentRoom.players ? this.currentRoom.players.length : 0;
            const max = this.currentRoom.max_players || 6;
            playerCount.textContent = `${current}/${max}`;
        }
        
        // Show room code for private rooms
        if (this.currentRoom.is_private && roomCodeDisplay && roomCode) {
            roomCodeDisplay.style.display = 'block';
            roomCode.textContent = this.currentRoom.room_code;
        }
        
        // Update players list
        if (playersList && this.currentRoom.players) {
            playersList.innerHTML = '';
            this.currentRoom.players.forEach(player => {
                const playerDiv = document.createElement('div');
                playerDiv.className = 'player-item';
                playerDiv.innerHTML = `
                    <div>
                        <span class="player-name">${player.nickname}</span>
                        ${player.is_host ? '<span class="host-badge">HOST</span>' : ''}
                    </div>
                    <span class="player-status ${player.is_connected ? 'connected' : 'disconnected'}">
                        ${player.is_connected ? '●' : '○'}
                    </span>
                `;
                playersList.appendChild(playerDiv);
            });
        }
        
        // Update start game button - always show for host
        if (startGameBtn) {
            // Check if current user is the host of this room
            const isHost = this.currentUser && this.currentRoom.host && 
                          (this.currentUser.id === this.currentRoom.host.id || this.currentUser.username === this.currentRoom.host.username);
            
            // Also check if currentPlayer is set and is host
            const isPlayerHost = this.currentPlayer && this.currentPlayer.is_host;
            
            const userIsHost = isHost || isPlayerHost;
            
            if (userIsHost) {
                startGameBtn.style.display = 'block';
                const playerCount = this.currentRoom.players ? this.currentRoom.players.length : 0;
                const canStart = playerCount >= 3;
                startGameBtn.disabled = !canStart;
                
                // Update button text based on player count
                if (playerCount < 3) {
                    startGameBtn.textContent = `Start Game (${playerCount}/3 players)`;
                } else {
                    startGameBtn.textContent = 'Start Game';
                }
            } else {
                startGameBtn.style.display = 'none';
            }
        }
        
        // Update close room button
        if (closeRoomBtn) {
            const canClose = (this.currentPlayer && this.currentPlayer.is_host) || 
                           (this.currentUser && this.currentUser.is_staff);
            closeRoomBtn.style.display = canClose ? 'inline-block' : 'none';
        }
    }
    
    async closeRoom() {
        if (!this.currentRoom || !confirm('Are you sure you want to close this room?')) {
            return;
        }
        
        try {
            const response = await fetch(`/api/rooms/${this.currentRoom.id}/close/`, {
                method: 'POST',
                headers: {
                    'Authorization': `Token ${this.authToken}`,
                    'Content-Type': 'application/json',
                    'X-CSRFToken': this.getCsrfToken()
                }
            });
            
            const data = await response.json();
            
            if (response.ok) {
                this.showNotification('Room closed successfully', 'success');
                this.showDashboard();
            } else {
                this.showNotification(data.error || 'Failed to close room', 'error');
            }
        } catch (error) {
            console.error('Error closing room:', error);
            this.showNotification('Failed to close room', 'error');
        }
    }
    
    updateGameUI() {
        if (!this.currentRound) return;
        
        // Update game phase
        const phaseElement = document.getElementById('gamePhase');
        if (phaseElement) {
            phaseElement.textContent = this.getPhaseText(this.currentRound.status);
        }
        
        // Update round info
        document.getElementById('currentRoundNumber').textContent = this.currentRoom.current_round;
        document.getElementById('totalRounds').textContent = this.currentRoom.total_rounds;
        
        // Handle different game phases
        this.handleGamePhase(this.currentRound.status);
    }
    
    getPhaseText(status) {
        const phases = {
            'answering': 'Answer the Question',
            'discussion': 'Discussion Time',
            'voting': 'Vote for the Imposter',
            'results': 'Round Results'
        };
        return phases[status] || status;
    }
    
    handleGamePhase(status) {
        // Hide all phase containers
        document.querySelectorAll('.game-phase').forEach(phase => {
            phase.classList.add('hidden');
        });
        
        // Show current phase
        const currentPhase = document.getElementById(`${status}Phase`);
        if (currentPhase) {
            currentPhase.classList.remove('hidden');
        }
        
        // Handle specific phases
        switch(status) {
            case 'answering':
                this.displayQuestion();
                break;
            case 'discussion':
                this.displayAnswers();
                break;
            case 'voting':
                this.displayVoting();
                break;
            case 'results':
                this.displayResults();
                break;
        }
    }
    
    displayQuestion() {
        if (!this.currentRound.question_text) return;
        
        const questionElement = document.getElementById('questionText');
        if (questionElement) {
            questionElement.textContent = this.currentRound.question_text;
        }
    }
    
    displayAnswers() {
        const answersContainer = document.getElementById('answersDisplay');
        if (!answersContainer || !this.currentRound.answers) return;
        
        answersContainer.innerHTML = '<h3>Submitted Answers:</h3>';
        const answersGrid = document.createElement('div');
        answersGrid.className = 'answers-with-names';
        
        // Sort answers for display
        const sortedAnswers = [...this.currentRound.answers].sort((a, b) => a.answer - b.answer);
        
        sortedAnswers.forEach(answer => {
            const answerCard = document.createElement('div');
            answerCard.className = 'answer-card-discussion';
            answerCard.innerHTML = `
                <div class="answer-number-large">${answer.answer}</div>
                <div class="answer-player-name">${answer.player.nickname}</div>
            `;
            answersGrid.appendChild(answerCard);
        });
        
        answersContainer.appendChild(answersGrid);
    }
    
    displayVoting() {
        const votingContainer = document.getElementById('votingOptions');
        if (!votingContainer || !this.currentRoom.players) return;
        
        votingContainer.innerHTML = '';
        
        this.currentRoom.players.forEach(player => {
            if (player.user.id !== this.currentUser.id) {
                const option = document.createElement('div');
                option.className = 'voting-option';
                option.innerHTML = `
                    <input type="radio" name="suspectPlayer" value="${player.id}" id="player_${player.id}">
                    <label for="player_${player.id}">${player.nickname}</label>
                `;
                votingContainer.appendChild(option);
            }
        });
    }
    
    displayResults() {
        // This will be called when results are available
        // Implementation depends on the results data structure
    }
    
    // Game Action Methods
    async startGame() {
        try {
            await this.apiCall(`/api/rooms/${this.currentRoom.id}/start/`, 'POST');
            this.showNotification('Game started!', 'success');
        } catch (error) {
            this.showNotification('Failed to start game', 'error');
        }
    }
    
    async handleSubmitAnswer(e) {
        e.preventDefault();
        const formData = new FormData(e.target);
        const answer = parseInt(formData.get('answer'));
        
        if (!answer || answer < 1) {
            this.showNotification('Please enter a valid answer', 'error');
            return;
        }
        
        try {
            await this.apiCall(`/api/rooms/${this.currentRoom.id}/submit-answer/`, 'POST', {
                answer: answer
            });
            this.showNotification('Answer submitted!', 'success');
            e.target.reset();
            
            // Disable form
            e.target.querySelector('input[name="answer"]').disabled = true;
            e.target.querySelector('button[type="submit"]').disabled = true;
        } catch (error) {
            this.showNotification('Failed to submit answer', 'error');
        }
    }
    
    async startVoting() {
        try {
            await this.apiCall(`/api/rooms/${this.currentRoom.id}/start-voting/`, 'POST');
            this.showNotification('Voting started!', 'success');
        } catch (error) {
            this.showNotification('Failed to start voting', 'error');
        }
    }
    
    async submitVote() {
        const selectedPlayer = document.querySelector('input[name="suspectPlayer"]:checked');
        if (!selectedPlayer) {
            this.showNotification('Please select a player to vote for', 'error');
            return;
        }
        
        try {
            const voteData = {
                accused_player_id: parseInt(selectedPlayer.value)
            };
            
            const result = await this.apiCall(`/api/rooms/${this.currentRoom.id}/submit-vote/`, 'POST', voteData);
            this.showNotification('Vote submitted!', 'success');
            
            // Disable voting
            document.querySelectorAll('input[name="suspectPlayer"]').forEach(input => {
                input.disabled = true;
            });
            document.getElementById('submitVoteBtn').disabled = true;
            
            // If voting is complete, show notification
            if (result.voting_complete) {
                this.showNotification('All votes submitted! Calculating results...', 'success');
            }
            
        } catch (error) {
            this.showNotification('Failed to submit vote', 'error');
        }
    }
    
    async continueToNextRound() {
        try {
            await this.apiCall(`/api/rooms/${this.currentRoom.id}/continue/`, 'POST');
            this.showNotification('Starting next round...', 'success');
        } catch (error) {
            this.showNotification('Failed to continue', 'error');
        }
    }
    
    showResults() {
        this.gameState = 'results';
        this.showScreen('resultsScreen');
        this.loadResults();
    }
    
    async loadResults() {
        try {
            const results = await this.apiCall(`/api/rooms/${this.currentRoom.id}/results/`);
            this.displayRoundResults(results);
        } catch (error) {
            console.error('Failed to load results:', error);
        }
    }
    
    displayRoundResults(results) {
        const resultsContainer = document.getElementById('resultsContent');
        if (!resultsContainer) return;
        
        resultsContainer.innerHTML = `
            <div class="imposter-reveal">
                <h3>🎭 The Imposter Was:</h3>
                <div class="imposter-name">${results.imposter_name}</div>
                ${results.imposter_caught ? '<p class="result-success">✅ Imposter was caught!</p>' : '<p class="result-failure">❌ Imposter escaped!</p>'}
            </div>
            
            <div class="questions-reveal">
                <div class="question-box detective-question">
                    <h4>🕵️ Detective Question (Real Question):</h4>
                    <p>${results.question_text}</p>
                </div>
                <div class="question-box imposter-question">
                    <h4>🎭 Imposter Question (Decoy Question):</h4>
                    <p>${results.decoy_question_text}</p>
                </div>
            </div>
            
            <div class="imposter-reveal-note">
                <p><strong>📝 Note:</strong> The imposter received the decoy question while detectives got the real question!</p>
            </div>
            
            <div class="answers-reveal">
                <h4>📊 Who Answered What:</h4>
                <div class="answers-with-players">
                    ${results.answers.map(answer => `
                        <div class="answer-player-card ${answer.player.id === results.imposter_id ? 'imposter' : 'detective'}">
                            <div class="answer-number">${answer.answer}</div>
                            <div class="player-info">
                                <span class="player-name">${answer.player.nickname}</span>
                                <span class="role-badge">${answer.player.id === results.imposter_id ? '🎭 Imposter' : '🕵️ Detective'}</span>
                            </div>
                        </div>
                    `).join('')}
                </div>
            </div>
            
            <div class="voting-results">
                <h4>🗳️ Voting Results:</h4>
                <div class="votes-breakdown">
                    ${results.votes.map(vote => `
                        <div class="vote-item">
                            <span class="voter">${vote.voter.nickname}</span> voted for 
                            <span class="accused">${vote.accused.nickname}</span>
                        </div>
                    `).join('')}
                </div>
            </div>
            
            <div class="scores-update">
                <h4>🏆 Updated Scores:</h4>
                <div class="scores-grid">
                    ${results.player_scores.map(score => `
                        <div class="score-card">
                            <div class="player-name">${score.player_name}</div>
                            <div class="score-change">+${score.points_earned} points</div>
                            <div class="total-score">Total: ${score.total_score}</div>
                        </div>
                    `).join('')}
                </div>
            </div>
        `;
    }
}

// Initialize the game when DOM is loaded
document.addEventListener('DOMContentLoaded', () => {
    window.game = new NumberHuntGame();
});
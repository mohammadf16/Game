// Admin Dashboard JavaScript
class AdminDashboard {
    constructor() {
        this.authToken = localStorage.getItem('authToken');
        this.currentUser = null;
        this.refreshInterval = null;
        
        this.initializeAdmin();
    }
    
    async initializeAdmin() {
        await this.checkAdminAuth();
        this.setupEventListeners();
        this.loadOverviewData();
        this.startAutoRefresh();
    }
    
    async checkAdminAuth() {
        if (!this.authToken) {
            this.redirectToLogin();
            return;
        }
        
        try {
            const user = await this.apiCall('/api/auth/profile/');
            this.currentUser = user.user;
            
            if (!this.currentUser.is_staff && !this.currentUser.is_superuser) {
                alert('Access denied. Admin privileges required.');
                this.redirectToLogin();
                return;
            }
        } catch (error) {
            this.redirectToLogin();
        }
    }
    
    redirectToLogin() {
        localStorage.removeItem('authToken');
        window.location.href = '/';
    }
    
    setupEventListeners() {
        // Tab navigation
        document.getElementById('overviewTab').addEventListener('click', () => this.showTab('overview'));
        document.getElementById('playersTab').addEventListener('click', () => this.showTab('players'));
        document.getElementById('gamesTab').addEventListener('click', () => this.showTab('games'));
        document.getElementById('statisticsTab').addEventListener('click', () => this.showTab('statistics'));
        document.getElementById('systemTab').addEventListener('click', () => this.showTab('system'));
        
        // Logout
        document.getElementById('logoutAdminBtn').addEventListener('click', () => this.logout());
        
        // Refresh buttons
        document.getElementById('refreshPlayers')?.addEventListener('click', () => this.loadPlayersData());
        document.getElementById('refreshGames')?.addEventListener('click', () => this.loadGamesData());
        
        // System actions
        document.getElementById('cleanupSessions')?.addEventListener('click', () => this.cleanupSessions());
        document.getElementById('cleanupGames')?.addEventListener('click', () => this.cleanupGames());
        document.getElementById('exportData')?.addEventListener('click', () => this.exportData());
        
        // Search and filters
        document.getElementById('playerSearch')?.addEventListener('input', (e) => this.filterPlayers(e.target.value));
        document.getElementById('gameStatusFilter')?.addEventListener('change', (e) => this.filterGames(e.target.value));
    }
    
    async apiCall(endpoint, method = 'GET', data = null) {
        const url = endpoint;
        const options = {
            method,
            headers: {
                'Content-Type': 'application/json',
                'Authorization': `Token ${this.authToken}`
            }
        };
        
        if (data) {
            options.body = JSON.stringify(data);
        }
        
        const response = await fetch(url, options);
        
        if (!response.ok) {
            if (response.status === 401) {
                this.redirectToLogin();
                return;
            }
            throw new Error(`HTTP ${response.status}: ${response.statusText}`);
        }
        
        return await response.json();
    }
    
    showTab(tabName) {
        // Hide all panels
        document.querySelectorAll('.admin-panel').forEach(panel => {
            panel.classList.remove('active');
        });
        
        // Remove active class from all tabs
        document.querySelectorAll('.tab-btn').forEach(btn => {
            btn.classList.remove('active');
        });
        
        // Show selected panel and activate tab
        document.getElementById(`${tabName}Panel`).classList.add('active');
        document.getElementById(`${tabName}Tab`).classList.add('active');
        
        // Load data for the selected tab
        switch(tabName) {
            case 'overview':
                this.loadOverviewData();
                break;
            case 'players':
                this.loadPlayersData();
                break;
            case 'games':
                this.loadGamesData();
                break;
            case 'statistics':
                this.loadStatisticsData();
                break;
            case 'system':
                this.loadSystemData();
                break;
        }
    }
    
    async loadOverviewData() {
        try {
            const stats = await this.apiCall('/api/admin/overview-stats/');
            
            document.getElementById('totalUsers').textContent = stats.total_users;
            document.getElementById('totalGames').textContent = stats.total_games;
            document.getElementById('activeGames').textContent = stats.active_games;
            document.getElementById('totalRounds').textContent = stats.total_rounds;
            
            this.loadRecentActivity();
            this.checkSystemHealth();
        } catch (error) {
            console.error('Failed to load overview data:', error);
        }
    }
    
    async loadRecentActivity() {
        try {
            const activities = await this.apiCall('/api/admin/recent-activity/');
            const container = document.getElementById('recentActivity');
            
            container.innerHTML = activities.map(activity => `
                <div class="activity-item">
                    <div class="activity-time">${this.formatTime(activity.timestamp)}</div>
                    <div class="activity-text">${activity.description}</div>
                </div>
            `).join('');
        } catch (error) {
            console.error('Failed to load recent activity:', error);
        }
    }
    
    async checkSystemHealth() {
        try {
            const health = await this.apiCall('/api/health-check/');
            document.getElementById('dbStatus').textContent = 'Online';
            document.getElementById('dbStatus').className = 'health-status online';
        } catch (error) {
            document.getElementById('dbStatus').textContent = 'Error';
            document.getElementById('dbStatus').className = 'health-status offline';
        }
    }
    
    async loadPlayersData() {
        try {
            const players = await this.apiCall('/api/admin/players/');
            const tbody = document.querySelector('#playersTable tbody');
            
            tbody.innerHTML = players.map(player => `
                <tr>
                    <td>${player.id}</td>
                    <td>${player.username}</td>
                    <td>${player.email}</td>
                    <td>${player.games_played}</td>
                    <td>${player.win_rate}%</td>
                    <td>${this.formatTime(player.last_active)}</td>
                    <td><span class="status-badge ${player.is_online ? 'status-online' : 'status-offline'}">${player.is_online ? 'Online' : 'Offline'}</span></td>
                    <td>
                        <button class="action-btn view" onclick="admin.viewPlayer(${player.id})">View</button>
                        <button class="action-btn edit" onclick="admin.editPlayer(${player.id})">Edit</button>
                        ${player.is_active ? 
                            `<button class="action-btn delete" onclick="admin.deactivatePlayer(${player.id})">Deactivate</button>` :
                            `<button class="action-btn edit" onclick="admin.activatePlayer(${player.id})">Activate</button>`
                        }
                    </td>
                </tr>
            `).join('');
        } catch (error) {
            console.error('Failed to load players data:', error);
        }
    }
    
    async loadGamesData() {
        try {
            const games = await this.apiCall('/api/admin/games/');
            const tbody = document.querySelector('#gamesTable tbody');
            
            tbody.innerHTML = games.map(game => `
                <tr>
                    <td>${game.id.substring(0, 8)}...</td>
                    <td>${game.name}</td>
                    <td>${game.host.username}</td>
                    <td>${game.player_count}/${game.max_players}</td>
                    <td><span class="status-badge status-${game.status.replace('_', '-')}">${game.status}</span></td>
                    <td>${game.current_round}/${game.total_rounds}</td>
                    <td>${this.formatTime(game.created_at)}</td>
                    <td>
                        <button class="action-btn view" onclick="admin.viewGame('${game.id}')">View</button>
                        ${game.status !== 'finished' ? 
                            `<button class="action-btn delete" onclick="admin.endGame('${game.id}')">End Game</button>` : ''
                        }
                    </td>
                </tr>
            `).join('');
        } catch (error) {
            console.error('Failed to load games data:', error);
        }
    }
    
    async loadStatisticsData() {
        try {
            const stats = await this.apiCall('/api/admin/detailed-stats/');
            
            // Load top players
            const topPlayersContainer = document.getElementById('topPlayers');
            topPlayersContainer.innerHTML = stats.top_players.map((player, index) => `
                <div class="leaderboard-item">
                    <span class="player-rank">#${index + 1}</span>
                    <span class="player-name">${player.username}</span>
                    <span class="player-score">${player.total_score} pts</span>
                </div>
            `).join('');
            
            // Load game metrics
            const metricsContainer = document.getElementById('gameMetrics');
            metricsContainer.innerHTML = `
                <div class="metric-item">
                    <span class="metric-label">Average Game Duration</span>
                    <span class="metric-value">${stats.avg_game_duration} min</span>
                </div>
                <div class="metric-item">
                    <span class="metric-label">Average Players per Game</span>
                    <span class="metric-value">${stats.avg_players_per_game}</span>
                </div>
                <div class="metric-item">
                    <span class="metric-label">Imposter Win Rate</span>
                    <span class="metric-value">${stats.imposter_win_rate}%</span>
                </div>
                <div class="metric-item">
                    <span class="metric-label">Most Active Hour</span>
                    <span class="metric-value">${stats.most_active_hour}:00</span>
                </div>
            `;
        } catch (error) {
            console.error('Failed to load statistics data:', error);
        }
    }
    
    async loadSystemData() {
        try {
            const systemInfo = await this.apiCall('/api/admin/system-info/');
            
            const dbInfoContainer = document.getElementById('databaseInfo');
            dbInfoContainer.innerHTML = `
                <div class="db-stat">
                    <div class="db-stat-number">${systemInfo.total_tables}</div>
                    <div class="db-stat-label">Database Tables</div>
                </div>
                <div class="db-stat">
                    <div class="db-stat-number">${systemInfo.total_records}</div>
                    <div class="db-stat-label">Total Records</div>
                </div>
                <div class="db-stat">
                    <div class="db-stat-number">${systemInfo.db_size}</div>
                    <div class="db-stat-label">Database Size</div>
                </div>
            `;
            
            // Load system logs
            document.getElementById('systemLogs').value = systemInfo.recent_logs.join('\n');
        } catch (error) {
            console.error('Failed to load system data:', error);
        }
    }
    
    // Player Management
    async viewPlayer(playerId) {
        try {
            const player = await this.apiCall(`/api/admin/players/${playerId}/`);
            alert(`Player Details:\nUsername: ${player.username}\nEmail: ${player.email}\nGames Played: ${player.games_played}\nWin Rate: ${player.win_rate}%`);
        } catch (error) {
            alert('Failed to load player details');
        }
    }
    
    async editPlayer(playerId) {
        // Implementation for editing player
        alert('Edit player functionality would be implemented here');
    }
    
    async deactivatePlayer(playerId) {
        if (confirm('Are you sure you want to deactivate this player?')) {
            try {
                await this.apiCall(`/api/admin/players/${playerId}/deactivate/`, 'POST');
                this.loadPlayersData();
                this.showNotification('Player deactivated successfully', 'success');
            } catch (error) {
                this.showNotification('Failed to deactivate player', 'error');
            }
        }
    }
    
    async activatePlayer(playerId) {
        try {
            await this.apiCall(`/api/admin/players/${playerId}/activate/`, 'POST');
            this.loadPlayersData();
            this.showNotification('Player activated successfully', 'success');
        } catch (error) {
            this.showNotification('Failed to activate player', 'error');
        }
    }
    
    // Game Management
    async viewGame(gameId) {
        try {
            const game = await this.apiCall(`/api/admin/games/${gameId}/`);
            alert(`Game Details:\nName: ${game.name}\nHost: ${game.host.username}\nPlayers: ${game.player_count}/${game.max_players}\nStatus: ${game.status}`);
        } catch (error) {
            alert('Failed to load game details');
        }
    }
    
    async endGame(gameId) {
        if (confirm('Are you sure you want to force end this game?')) {
            try {
                await this.apiCall(`/api/admin/games/${gameId}/end/`, 'POST');
                this.loadGamesData();
                this.showNotification('Game ended successfully', 'success');
            } catch (error) {
                this.showNotification('Failed to end game', 'error');
            }
        }
    }
    
    // System Management
    async cleanupSessions() {
        if (confirm('Are you sure you want to cleanup old sessions?')) {
            try {
                const result = await this.apiCall('/api/admin/cleanup-sessions/', 'POST');
                this.showNotification(result.message, 'success');
            } catch (error) {
                this.showNotification('Failed to cleanup sessions', 'error');
            }
        }
    }
    
    async cleanupGames() {
        if (confirm('Are you sure you want to cleanup old finished games?')) {
            try {
                const result = await this.apiCall('/api/admin/cleanup-games/', 'POST');
                this.showNotification(result.message, 'success');
            } catch (error) {
                this.showNotification('Failed to cleanup games', 'error');
            }
        }
    }
    
    async exportData() {
        try {
            const response = await fetch('/api/admin/export-data/', {
                headers: {
                    'Authorization': `Token ${this.authToken}`
                }
            });
            
            if (response.ok) {
                const blob = await response.blob();
                const url = window.URL.createObjectURL(blob);
                const a = document.createElement('a');
                a.href = url;
                a.download = `numberhunt_data_${new Date().toISOString().split('T')[0]}.json`;
                document.body.appendChild(a);
                a.click();
                window.URL.revokeObjectURL(url);
                document.body.removeChild(a);
                this.showNotification('Data exported successfully', 'success');
            } else {
                throw new Error('Export failed');
            }
        } catch (error) {
            this.showNotification('Failed to export data', 'error');
        }
    }
    
    // Filtering
    filterPlayers(searchTerm) {
        const rows = document.querySelectorAll('#playersTable tbody tr');
        rows.forEach(row => {
            const username = row.cells[1].textContent.toLowerCase();
            const email = row.cells[2].textContent.toLowerCase();
            const matches = username.includes(searchTerm.toLowerCase()) || 
                          email.includes(searchTerm.toLowerCase());
            row.style.display = matches ? '' : 'none';
        });
    }
    
    filterGames(status) {
        const rows = document.querySelectorAll('#gamesTable tbody tr');
        rows.forEach(row => {
            const gameStatus = row.cells[4].textContent.toLowerCase();
            const matches = !status || gameStatus.includes(status.toLowerCase());
            row.style.display = matches ? '' : 'none';
        });
    }
    
    // Utility Methods
    formatTime(timestamp) {
        if (!timestamp) return 'Never';
        const date = new Date(timestamp);
        return date.toLocaleString();
    }
    
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
    
    startAutoRefresh() {
        this.refreshInterval = setInterval(() => {
            const activePanel = document.querySelector('.admin-panel.active');
            if (activePanel && activePanel.id === 'overviewPanel') {
                this.loadOverviewData();
            }
        }, 30000); // Refresh every 30 seconds
    }
    
    async logout() {
        try {
            await this.apiCall('/api/auth/logout/', 'POST');
        } catch (error) {
            // Ignore logout errors
        }
        
        localStorage.removeItem('authToken');
        window.location.href = '/';
    }
}

// Initialize admin dashboard when DOM is loaded
document.addEventListener('DOMContentLoaded', () => {
    window.admin = new AdminDashboard();
});

#database.py
import sqlite3
from datetime import datetime
from typing import List, Tuple, Optional, Dict

class Database:
    def __init__(self, db_file: str = "tournament.db"):
        self.db_file = db_file
        self.init_db()

    def init_db(self):
        with sqlite3.connect(self.db_file) as conn:
            cursor = conn.cursor()
            
            # Таблица команд
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS teams (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    team_name TEXT NOT NULL,
                    captain_contact TEXT NOT NULL,
                    registration_date TIMESTAMP NOT NULL,
                    status TEXT DEFAULT 'pending',
                    admin_comment TEXT
                )
            ''')
            
            # Таблица игроков
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS players (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    team_id INTEGER,
                    nickname TEXT NOT NULL,
                    telegram_username TEXT NOT NULL,
                    telegram_id INTEGER,  -- Добавлено поле telegram_id
                    is_captain BOOLEAN DEFAULT 0,
                    FOREIGN KEY (team_id) REFERENCES teams (id)
                )
            ''')
            
            # Таблица администраторов
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS admins (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    telegram_id INTEGER UNIQUE NOT NULL,
                    username TEXT,
                    added_date TIMESTAMP NOT NULL
                )
            ''')
            
            conn.commit()

    def register_team(self, team_name: str, players: List[Dict[str, str]], captain_contact: str) -> int:
        with sqlite3.connect(self.db_file) as conn:
            cursor = conn.cursor()
            
            # Добавляем команду
            cursor.execute('''
                INSERT INTO teams (team_name, captain_contact, registration_date)
                VALUES (?, ?, ?)
            ''', (team_name, captain_contact, datetime.utcnow()))
            
            team_id = cursor.lastrowid
            
            # Добавляем игроков
            for player in players:
                cursor.execute('''
                    INSERT INTO players (team_id, nickname, telegram_username, telegram_id, is_captain)
                    VALUES (?, ?, ?, ?, ?)
                ''', (team_id, player['nickname'], player['username'], player['telegram_id'], player['is_captain']))
            
            conn.commit()
            return team_id

    def get_team_status(self, team_name: str) -> Optional[dict]:
        with sqlite3.connect(self.db_file) as conn:
            cursor = conn.cursor()
            
            cursor.execute('''
                SELECT t.id, t.team_name, t.status, t.registration_date, t.admin_comment
                FROM teams t
                WHERE t.team_name = ?
            ''', (team_name,))
            
            team = cursor.fetchone()
            if not team:
                return None
                
            cursor.execute('''
                SELECT nickname, telegram_username, telegram_id
                FROM players
                WHERE team_id = ?
            ''', (team[0],))
            
            players = cursor.fetchall()
            
            return {
                'team_name': team[1],
                'status': team[2],
                'registration_date': team[3],
                'admin_comment': team[4],
                'players': players
            }
    
    def get_team_by_telegram_id(self, telegram_id: int) -> Optional[dict]:
        with sqlite3.connect(self.db_file) as conn:
            cursor = conn.cursor()
            
            # Находим team_id по telegram_id игрока
            cursor.execute('''
                SELECT team_id FROM players WHERE telegram_id = ?
            ''', (telegram_id,))
            
            player = cursor.fetchone()
            if not player:
                return None
            
            team_id = player[0]
            
            # Получаем информацию о команде по team_id
            cursor.execute('''
                SELECT t.id, t.team_name, t.status, t.registration_date, t.admin_comment
                FROM teams t
                WHERE t.id = ?
            ''', (team_id,))
            
            team = cursor.fetchone()
            if not team:
                return None
            
            # Получаем информацию об игроках команды
            cursor.execute('''
                SELECT nickname, telegram_username, telegram_id
                FROM players
                WHERE team_id = ?
            ''', (team_id,))
            
            players = cursor.fetchall()
            
            return {
                'team_name': team[1],
                'status': team[2],
                'registration_date': team[3],
                'admin_comment': team[4],
                'players': players
            }

    def add_admin(self, telegram_id: int, username: str) -> bool:
        try:
            with sqlite3.connect(self.db_file) as conn:
                cursor = conn.cursor()
                cursor.execute('''
                    INSERT INTO admins (telegram_id, username, added_date)
                    VALUES (?, ?, ?)
                ''', (telegram_id, username, datetime.utcnow()))
                conn.commit()
                return True
        except sqlite3.IntegrityError:
            return False

    def is_admin(self, telegram_id: int) -> bool:
        with sqlite3.connect(self.db_file) as conn:
            cursor = conn.cursor()
            cursor.execute('SELECT 1 FROM admins WHERE telegram_id = ?', (telegram_id,))
            return cursor.fetchone() is not None

    def update_team_status(self, team_id: int, status: str, comment: str = None) -> bool:
        with sqlite3.connect(self.db_file) as conn:
            cursor = conn.cursor()
            if comment:
                cursor.execute('''
                    UPDATE teams 
                    SET status = ?, admin_comment = ?
                    WHERE id = ?
                ''', (status, comment, team_id))
            else:
                cursor.execute('''
                    UPDATE teams 
                    SET status = ?
                    WHERE id = ?
                ''', (status, team_id))
            conn.commit()
            return cursor.rowcount > 0
        
    def team_name_exists(self, team_name: str) -> bool:
        with sqlite3.connect(self.db_file) as conn:
            cursor = conn.cursor()
            cursor.execute('''
                SELECT 1 FROM teams WHERE LOWER(team_name) = LOWER(?)
            ''', (team_name.lower(),))  # Приводим к нижнему регистру
            return cursor.fetchone() is not None

    def get_all_teams(self) -> List[dict]:
        with sqlite3.connect(self.db_file) as conn:
            cursor = conn.cursor()
            cursor.execute('''
                SELECT t.id, t.team_name, t.status, t.registration_date, t.captain_contact, t.admin_comment
                FROM teams t
                ORDER BY t.registration_date DESC
            ''')
            
            teams = []
            for team in cursor.fetchall():
                cursor.execute('''
                    SELECT nickname, telegram_username, telegram_id
                    FROM players
                    WHERE team_id = ?
                ''', (team[0],))
                
                players = cursor.fetchall()
                teams.append({
                    'id': team[0],
                    'team_name': team[1],
                    'status': team[2],
                    'registration_date': team[3],
                    'captain_contact': team[4],
                    'admin_comment': team[5],
                    'players': players
                })
            
            return teams
    
    def get_all_teams_by_status(self, status: str) -> List[dict]:
        with sqlite3.connect(self.db_file) as conn:
            cursor = conn.cursor()
            cursor.execute('''
                SELECT t.id, t.team_name, t.status, t.registration_date, t.captain_contact, t.admin_comment
                FROM teams t
                WHERE t.status = ?
                ORDER BY t.registration_date DESC
            ''', (status,))
            
            teams = []
            for team in cursor.fetchall():
                cursor.execute('''
                    SELECT nickname, telegram_username, telegram_id
                    FROM players
                    WHERE team_id = ?
                ''', (team[0],))
                
                players = cursor.fetchall()
                teams.append({
                    'id': team[0],
                    'team_name': team[1],
                    'status': team[2],
                    'registration_date': team[3],
                    'captain_contact': team[4],
                    'admin_comment': team[5],
                    'players': players
                })
            
            return teams

    def get_teams_count_by_status(self, status: str) -> int:
        with sqlite3.connect(self.db_file) as conn:
            cursor = conn.cursor()
            cursor.execute('''
                SELECT COUNT(*) FROM teams WHERE status = ?
            ''', (status,))
            return cursor.fetchone()[0]

    def update_team_comment(self, team_id: int, comment: str) -> bool:
        with sqlite3.connect(self.db_file) as conn:
            cursor = conn.cursor()
            cursor.execute('''
                UPDATE teams
                SET admin_comment = ?
                WHERE id = ?
            ''', (comment, team_id))
            conn.commit()
            return cursor.rowcount > 0
            
    # Новые методы для статистики
    def get_stats(self) -> dict:
        """Получить статистику о командах и игроках."""
        with sqlite3.connect(self.db_file) as conn:
            cursor = conn.cursor()
            
            # Общее количество команд
            cursor.execute('SELECT COUNT(*) FROM teams')
            total_teams = cursor.fetchone()[0]
            
            # Количество команд по статусам
            cursor.execute('SELECT status, COUNT(*) FROM teams GROUP BY status')
            status_counts = {status: count for status, count in cursor.fetchall()}
            
            # Общее количество игроков
            cursor.execute('SELECT COUNT(*) FROM players')
            total_players = cursor.fetchone()[0]
            
            # Среднее количество игроков в команде
            avg_players = total_players / total_teams if total_teams > 0 else 0
            
            # Количество игроков в командах с разными статусами
            cursor.execute('''
                SELECT t.status, COUNT(p.id)
                FROM teams t
                JOIN players p ON t.id = p.team_id
                GROUP BY t.status
            ''')
            players_by_status = {status: count for status, count in cursor.fetchall()}
            
            # Последние регистрации
            cursor.execute('''
                SELECT team_name, registration_date
                FROM teams
                ORDER BY registration_date DESC
                LIMIT 5
            ''')
            recent_registrations = [
                {'team_name': team_name, 'date': date}
                for team_name, date in cursor.fetchall()
            ]
            
            # Количество администраторов
            cursor.execute('SELECT COUNT(*) FROM admins')
            admin_count = cursor.fetchone()[0]
            
            return {
                'total_teams': total_teams,
                'teams_by_status': status_counts,
                'total_players': total_players,
                'avg_players_per_team': avg_players,
                'players_by_status': players_by_status,
                'recent_registrations': recent_registrations,
                'admin_count': admin_count
            }
            
    def get_admins(self) -> List[dict]:
        """Получить список всех администраторов."""
        with sqlite3.connect(self.db_file) as conn:
            cursor = conn.cursor()
            cursor.execute('''
                SELECT telegram_id, username, added_date
                FROM admins
                ORDER BY added_date DESC
            ''')
            
            return [
                {'telegram_id': tid, 'username': username, 'added_date': date}
                for tid, username, date in cursor.fetchall()
            ]
            
    def remove_admin(self, telegram_id: int) -> bool:
        """Удалить администратора по его Telegram ID."""
        with sqlite3.connect(self.db_file) as conn:
            cursor = conn.cursor()
            cursor.execute('DELETE FROM admins WHERE telegram_id = ?', (telegram_id,))
            conn.commit()
            return cursor.rowcount > 0
            
    def get_daily_registrations(self, days: int = 7) -> List[Tuple[str, int]]:
        """Получить статистику регистраций по дням за последние N дней."""
        with sqlite3.connect(self.db_file) as conn:
            conn.create_function("DATE", 1, lambda timestamp: timestamp.split()[0])
            cursor = conn.cursor()
            cursor.execute('''
                SELECT DATE(registration_date) as reg_date, COUNT(*) as count
                FROM teams
                GROUP BY DATE(registration_date)
                ORDER BY reg_date DESC
                LIMIT ?
            ''', (days,))
            
            return cursor.fetchall()

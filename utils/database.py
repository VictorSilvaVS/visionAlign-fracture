import sqlite3
import hashlib
from pathlib import Path
from datetime import datetime, timedelta, timezone
import logging
from .timezone_utils import get_current_timestamp_for_storage, get_current_utc_timestamp, format_datetime_for_storage
from werkzeug.security import check_password_hash, generate_password_hash


class Database:
    def __init__(self, db_path=None):
        if db_path:
            self.db_path = Path(db_path)
        else:
            self.db_path = Path(__file__).parent.parent / 'data' / 'users.db' 
        self.db_path.parent.mkdir(exist_ok=True)
        self.conn = sqlite3.connect(str(self.db_path), check_same_thread=False)
        self.logger = logging.getLogger('VisionAlign.Database')
        self.create_tables()
    def get_activity_since(self, timestamp_threshold):
        try:
            cursor = self.conn.cursor()
            threshold_str = timestamp_threshold.strftime('%Y-%m-%d %H:%M:%S')
            cursor.execute("""
                SELECT id, timestamp, username, ip_address, action, details 
                FROM activity_log
                WHERE timestamp >= ?
                ORDER BY timestamp DESC
            """, (threshold_str,))
            logs = cursor.fetchall()
            return logs
        except sqlite3.Error as e:
            print(f"Erro ao buscar logs de atividade: {e}")
            return []
    def create_tables(self):
        with self.conn:
            self.conn.execute('''
                CREATE TABLE IF NOT EXISTS users (  
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    username TEXT UNIQUE NOT NULL,
                    password TEXT NOT NULL,
                    email TEXT UNIQUE NOT NULL,
                    first_name TEXT,
                    last_name TEXT,
                    is_admin INTEGER DEFAULT 0,
                    created_at TEXT NOT NULL
                )
            ''')
            self.conn.execute('''
                CREATE TABLE IF NOT EXISTS activity_log (
                    id INTEGER PRIMARY KEY AUTOINCREMENT, 
                    timestamp TEXT NOT NULL, -- Armazenar como TEXT (ISO8601 UTC)
                    username TEXT, 
                    ip_address TEXT,
                    action TEXT NOT NULL,
                    details TEXT
                )
                              
            ''')
            # <<< NOVO: Criação da tabela de Alertas >>>
            self.conn.execute('''
                CREATE TABLE IF NOT EXISTS alerts (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    timestamp TEXT NOT NULL,
                    type TEXT NOT NULL,
                    lata_id TEXT,
                    details TEXT
                )
                                
            ''') 
            self.conn.execute('''
                CREATE TABLE IF NOT EXISTS detection_log (
                    id INTEGER PRIMARY KEY AUTOINCREMENT, 
                    timestamp TEXT NOT NULL, -- Armazenar como TEXT (ISO8601 UTC)
                    normal_count INTEGER DEFAULT 0, 
                    inverted_count INTEGER DEFAULT 0,
                    fallen_count INTEGER DEFAULT 0,
                    fracture_count INTEGER DEFAULT 0
                )
            ''')
            # Tabela para reset de senha
            self.conn.execute('''
                CREATE TABLE IF NOT EXISTS password_resets (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id INTEGER NOT NULL,
                    token TEXT UNIQUE NOT NULL,
                    expires_at TEXT NOT NULL,
                    used INTEGER DEFAULT 0,
                    FOREIGN KEY (user_id) REFERENCES users (id)
                )
            ''')
            # Migrações: adicionar colunas se não existirem
            try:
                cursor = self.conn.cursor()
                
                # Para detection_log: fracture_count
                cursor.execute("PRAGMA table_info(detection_log)")
                columns = [col[1] for col in cursor.fetchall()]
                if 'fracture_count' not in columns:
                    self.conn.execute('ALTER TABLE detection_log ADD COLUMN fracture_count INTEGER DEFAULT 0')
                    self.logger.info("Coluna 'fracture_count' adicionada à tabela detection_log")
                
                # Para users: email_notifications
                cursor.execute("PRAGMA table_info(users)")
                columns = [col[1] for col in cursor.fetchall()]
                if 'email_notifications' not in columns:
                    self.conn.execute('ALTER TABLE users ADD COLUMN email_notifications INTEGER DEFAULT 0')
                    self.logger.info("Coluna 'email_notifications' adicionada à tabela users")

            except Exception as e:
                self.logger.warning(f"Erro em migrações: {e}")
            self.conn.commit()
            self.logger.info("Tabelas do banco de dados verificadas/criadas com sucesso.")
    def get_daily_counts(self, target_date):
        try:
            start_datetime_obj_utc = datetime.combine(target_date, datetime.min.time()).replace(tzinfo=timezone.utc)
            end_datetime_obj_utc = datetime.combine(target_date, datetime.max.time()).replace(tzinfo=timezone.utc)
            start_datetime_utc_str = format_datetime_for_storage(start_datetime_obj_utc)
            end_datetime_utc_str = format_datetime_for_storage(end_datetime_obj_utc)


            query = """
                SELECT SUM(normal_count), SUM(inverted_count), SUM(fallen_count), SUM(COALESCE(fracture_count, 0))
                FROM detection_log
                WHERE timestamp BETWEEN ? AND ?
            """
            cursor = self.conn.cursor()
            cursor.execute(query, (start_datetime_utc_str, end_datetime_utc_str))
            result = cursor.fetchone()
            return {'normal': result[0] or 0, 'inverted': result[1] or 0, 'fallen': result[2] or 0, 'fracture': result[3] or 0} if result else {'normal': 0, 'inverted': 0, 'fallen': 0, 'fracture': 0}
        except sqlite3.Error as e:
            self.logger.error(f"Erro ao buscar contagens diárias para {target_date}: {e}")
            return None
    def log_detection_counts(self, normal_count, inverted_count, fallen_count, fracture_count=0):
        """Registra as contagens atuais de detecção no histórico."""
        try:
            current_ts_str = get_current_timestamp_for_storage()
            with self.conn:     
                self.conn.execute('''  
                    INSERT INTO detection_log (timestamp, normal_count, inverted_count, fallen_count, fracture_count)
                    VALUES (?, ?, ?, ?, ?)
                ''', (current_ts_str, normal_count, inverted_count, fallen_count, fracture_count))
            self.logger.debug(f"Contagens de detecção registradas: N={normal_count}, I={inverted_count}, F={fallen_count}, FR={fracture_count}")
            return True
        except sqlite3.Error as e:
            self.logger.error(f"Erro ao registrar contagens de detecção: {e}")
            return False

    # <<< NOVO: Método para buscar histórico de detecção >>>
    def get_detection_history(self, period_minutes=60):
        try:
            time_threshold_utc = get_current_utc_timestamp() - timedelta(minutes=period_minutes)
            time_threshold_str = get_current_timestamp_for_storage(time_threshold_utc)
            cursor = self.conn.cursor()
            cursor.execute('''
            SELECT timestamp, normal_count, inverted_count, fallen_count, COALESCE(fracture_count, 0)
            FROM detection_log
            WHERE timestamp >= ?
            ORDER BY timestamp ASC
            ''', (time_threshold_str,))
            history = cursor.fetchall()
            self.logger.debug(f"Histórico de detecção buscado para os últimos {period_minutes} minutos. {len(history)} registros encontrados.")
            return history
        except sqlite3.Error as e:
            self.logger.error(f"Erro ao buscar histórico de detecção: {e}")
            return []
        finally: 
            if 'cursor' in locals() and cursor: cursor.close()

    def get_aggregated_detection_data(self, period_type='hour', num_periods=24):
        """
        Busca dados de detecção agregados por um período específico.
        :param period_type: 'hour', 'day', 'week', 'month', 'year'
        :param num_periods: Quantos períodos para retornar (ex: 24 horas, 7 dias)
        :return: Lista de tuplas (label_periodo, normal_sum, inverted_sum, fallen_sum, total_sum)
        """
        self.logger.info(f"DB: Chamado get_aggregated_detection_data com period_type='{period_type}', num_periods={num_periods}")
        cursor = None
        try:
            cursor = self.conn.cursor()
            results = []
            raw_data = []
            if period_type == 'hour':
                date_format_group = "%Y-%m-%d %H:00"
                date_format_label = "%H:00"
                end_time_utc = get_current_utc_timestamp()
                start_time_limit_utc = end_time_utc - timedelta(hours=num_periods)
                
                query = f"""
                    SELECT 
                        strftime('{date_format_group}', timestamp) as period_group,
                        SUM(normal_count) as normal,
                        SUM(inverted_count) as inverted,
                        SUM(fallen_count) as fallen,
                        SUM(COALESCE(fracture_count, 0)) as fracture
                    FROM detection_log
                    WHERE timestamp >= ? AND timestamp <= ?
                    GROUP BY period_group
                    ORDER BY period_group DESC 
                    LIMIT ? 
                """
                params = (get_current_timestamp_for_storage(start_time_limit_utc),
                          get_current_timestamp_for_storage(end_time_utc),
                          num_periods)
                self.logger.debug(f"DB: Query para 'hour': {query.strip()} \nParams: {params}")
                cursor.execute(query, params)
                raw_data = cursor.fetchall()
                for row_desc in reversed(raw_data):
                    period_group_dt = datetime.strptime(row_desc[0], '%Y-%m-%d %H:00')
                    label = period_group_dt.strftime(date_format_label)
                    results.append((label, row_desc[1] or 0, row_desc[2] or 0, row_desc[3] or 0, (row_desc[1] or 0) + (row_desc[2] or 0) + (row_desc[3] or 0) + (row_desc[4] or 0), row_desc[4] or 0))

            elif period_type == 'day':
                date_format_group = "%Y-%m-%d"
                date_format_label = "%d/%m"
                current_utc = get_current_utc_timestamp()
                today_end_of_day_utc = current_utc.replace(hour=23, minute=59, second=59, microsecond=999999)
                end_time_utc = today_end_of_day_utc
                start_time_limit_utc = (today_end_of_day_utc - timedelta(days=num_periods - 1)).replace(hour=0, minute=0, second=0, microsecond=0)
                query = f"""
                    SELECT strftime('{date_format_group}', timestamp) as period_group, SUM(normal_count), SUM(inverted_count), SUM(fallen_count), SUM(COALESCE(fracture_count, 0))
                    FROM detection_log WHERE timestamp >= ? AND timestamp <= ?
                    GROUP BY period_group ORDER BY period_group DESC LIMIT ?
                """
                params = (get_current_timestamp_for_storage(start_time_limit_utc), get_current_timestamp_for_storage(end_time_utc), num_periods)
                self.logger.debug(f"DB: Query para 'day': {query.strip()} \nParams: {params}")
                cursor.execute(query, params)
                raw_data = cursor.fetchall()
                for row_desc in reversed(raw_data):
                    period_group_dt = datetime.strptime(row_desc[0], '%Y-%m-%d')
                    label = period_group_dt.strftime(date_format_label)
                    results.append((label, row_desc[1] or 0, row_desc[2] or 0, row_desc[3] or 0, (row_desc[1] or 0) + (row_desc[2] or 0) + (row_desc[3] or 0) + (row_desc[4] or 0), row_desc[4] or 0))
            elif period_type == 'month':
                date_format_group = "%Y-%m"
                date_format_label = "%m/%Y"
                current_utc = get_current_utc_timestamp()
                today_end_of_day_utc = current_utc.replace(hour=23, minute=59, second=59, microsecond=999999)
                end_time_utc = today_end_of_day_utc
                start_time_limit_utc = (today_end_of_day_utc.replace(day=1) - timedelta(days=sum(30 for _ in range(num_periods-1)))).replace(day=1, hour=0, minute=0, second=0, microsecond=0)
                query = f"""
                    SELECT strftime('{date_format_group}', timestamp) as period_group,
                           SUM(normal_count), SUM(inverted_count), SUM(fallen_count), SUM(COALESCE(fracture_count, 0))
                    FROM detection_log
                    WHERE timestamp >= ? AND timestamp <= ?
                    GROUP BY period_group
                    ORDER BY period_group DESC
                    LIMIT ?
                """
                params = (get_current_timestamp_for_storage(start_time_limit_utc),
                          get_current_timestamp_for_storage(end_time_utc), num_periods)
                self.logger.debug(f"DB: Query para 'month': {query.strip()} \nParams: {params}")
                cursor.execute(query, params)
                raw_data = cursor.fetchall()
                for row_desc in reversed(raw_data):
                    try:
                        period_group_dt = datetime.strptime(row_desc[0], '%Y-%m')
                        label = period_group_dt.strftime(date_format_label)
                        results.append((label, row_desc[1] or 0, row_desc[2] or 0, row_desc[3] or 0, (row_desc[1] or 0) + (row_desc[2] or 0) + (row_desc[3] or 0) + (row_desc[4] or 0), row_desc[4] or 0))
                    except ValueError:
                        self.logger.warning(f"Não foi possível analisar o period_group '{row_desc[0]}' para o tipo de período 'month'.")
            else:
                self.logger.warning(f"DB: Tipo de período não suportado '{period_type}' em get_aggregated_detection_data. Nenhum dado será retornado.")

            self.logger.info(f"DB: Dados agregados brutos retornados pela query ({len(raw_data)} registros): {raw_data}")
            self.logger.info(f"DB: Dados agregados processados para período '{period_type}' ({num_periods}): {len(results)} pontos. Resultados: {results}")
            return results
        except sqlite3.Error as e:
            self.logger.error(f"Erro ao buscar dados de detecção agregados: {e}", exc_info=True)
            return []
        finally:
            if cursor: cursor.close()
    def get_kpis_last_hour(self):
        """Calcula KPIs básicos da última hora."""
        history = self.get_detection_history(period_minutes=60)
        if not history:
            return {'total': 0, 'errors': 0, 'error_rate': 0.0}

        total_detections = 0
        total_errors = 0
        for _, normal, inverted, fallen, fracture in history:
            frame_total = normal + inverted + fallen + fracture
            total_detections += frame_total
            total_errors += inverted + fallen + fracture

        error_rate = (total_errors / total_detections * 100) if total_detections > 0 else 0.0
        return {'total': total_detections, 'errors': total_errors, 'error_rate': round(error_rate, 1)}
    
    def create_admin(self):
        """Cria usuário admin padrão se não existir"""
        if not self.get_user('admin'):
            self.add_user('admin', 'admin123', True)

    def add_user(self, username, password, is_admin=False):
        hashed = generate_password_hash(password)
        email_default = f"{username.lower().replace(' ', '.')}@example.com"
        first_name_default = username.capitalize()
        last_name_default = "User"
        is_admin_int = 1 if is_admin else 0
        return self.create_user(username, hashed, email_default, first_name_default, last_name_default, is_admin_int)

    def verify_user(self, username, password):
        """Verifica o nome de usuário e a senha usando o hash armazenado (com suporte a migração de SHA-256)."""
        cursor = self.conn.execute(
            'SELECT id, username, password, is_admin, first_name, last_name FROM users WHERE username = ?',
            (username,)
        )
        user = cursor.fetchone()

        if user:
            user_id, db_username, stored_password_hash, is_admin_flag, first_name, last_name = user
            
            # 1. Tentar verificação padrão (Werkzeug)
            try:
                if check_password_hash(stored_password_hash, password):
                    self.logger.info(f"Senha verificada (Werkzeug) para usuário '{username}'.")
                    return {
                        'id': user_id, 'username': db_username, 'is_admin': bool(is_admin_flag),
                        'first_name': first_name, 'last_name': last_name
                    }
            except Exception:
                pass # Não é um hash Werkzeug válido

            # 2. Fallback para SHA-256 legado e migração automática
            import hashlib
            legacy_hash = hashlib.sha256(password.encode()).hexdigest()
            if stored_password_hash == legacy_hash:
                self.logger.info(f"Detectada senha legada (SHA-256) para '{username}'. Migrando...")
                new_hash = generate_password_hash(password)
                self.update_user_password(user_id, new_hash)
                return {
                    'id': user_id, 'username': db_username, 'is_admin': bool(is_admin_flag),
                    'first_name': first_name, 'last_name': last_name
                }
                
        self.logger.warning(f"Falha na verificação de senha para o usuário '{username}'.")
        return None

    def log_activity(self, username, ip_address, action, details=None):
        """Registra uma atividade no log."""
        try:
            current_ts_str = get_current_timestamp_for_storage()
            with self.conn:
                self.conn.execute(
                    'INSERT INTO activity_log (timestamp, username, ip_address, action, details) VALUES (?, ?, ?, ?, ?)',
                    (current_ts_str, username, ip_address, action, details)
                )
        except Exception as e:
            print(f"Erro ao registrar log no banco de dados: {e}")
    def get_user(self, username):
        """Busca os dados de um usuário pelo username."""
        cursor = self.conn.execute(
            'SELECT id, username, is_admin, email, first_name, last_name FROM users WHERE username = ?',
            (username,)
        )
        user = cursor.fetchone()
        if user:
            user_id, db_username, is_admin_flag, email, first_name, last_name = user
            return {
                'id': user_id,
                'username': db_username,
                'is_admin': bool(is_admin_flag),
                'email': email,
                'first_name': first_name,
                'last_name': last_name
            }
        return None
    def get_recent_alerts(self, limit=20):
        """Busca os alertas mais recentes do banco de dados."""
        cursor = self.conn.cursor()
        try:
            cursor.execute("""
                SELECT id, timestamp, type, lata_id, details 
                FROM alerts 
                ORDER BY timestamp DESC 
                LIMIT ?
            """, (limit,))
            alerts = cursor.fetchall()
            self.logger.info(f"Buscados {len(alerts)} alertas recentes.")
            return alerts
        except sqlite3.Error as e:
            self.logger.error(f"Erro ao buscar alertas recentes do DB: {e}")
            return []
        finally:
            if cursor: cursor.close()
    def log_alert(self, timestamp, alert_type, lata_id, details):
        """Registra um alerta no banco de dados."""
        cursor = self.conn.cursor()
        try:
            cursor.execute("""
                INSERT INTO alerts (timestamp, type, lata_id, details)
                VALUES (?, ?, ?, ?)
            """, (timestamp, alert_type, lata_id, details))
            self.conn.commit()
            self.logger.info(f"Alerta registrado: Tipo {alert_type}, Lata {lata_id}, Detalhes: {details}")
        except sqlite3.Error as e:
            self.logger.error(f"Erro ao registrar alerta no DB: {e}")
        finally:
            if cursor: cursor.close()
    def close(self):
        self.conn.close()
        self.logger.info("Conexão com o banco de dados fechada.")

    def get_alerts_with_filters(self, start_date=None, end_date=None, alert_type=None, lata_id=None,
                                page=1, per_page=20,
                                order_by='timestamp', order_direction='DESC'):
        cursor = None
        try:
            cursor = self.conn.cursor()

            base_query_select_fields = "SELECT id, timestamp, type, lata_id, details"
            base_query_from = "FROM alerts"
            conditions = []

            data_params = []
            count_params = []

            if start_date and start_date.lower() != 'none' and start_date.strip() != '':
                start_date_dt_str = start_date
                if len(start_date) == 10:
                    start_date_dt_str += " 00:00:00"
                conditions.append("timestamp >= ?")
                data_params.append(start_date_dt_str)
                count_params.append(start_date_dt_str)
            
            if end_date and end_date.lower() != 'none' and end_date.strip() != '':
                end_date_dt_str = end_date
                if len(end_date) == 10:
                    end_date_dt_str += " 23:59:59"
                conditions.append("timestamp <= ?")
                data_params.append(end_date_dt_str)
                count_params.append(end_date_dt_str)

            if alert_type and alert_type.lower() != 'none' and alert_type.strip() != '':
                conditions.append("type = ?")
                data_params.append(alert_type)
                count_params.append(alert_type)
            
            if lata_id and lata_id.lower() != 'none' and lata_id.strip() != '':
                conditions.append("lata_id = ?") 
                data_params.append(lata_id)
                count_params.append(lata_id)

            where_clause = ""
            if conditions:
                where_clause = " WHERE " + " AND ".join(conditions)
            
            count_query = f"SELECT COUNT(id) {base_query_from} {where_clause}"
            self.logger.info(f"Executando query de contagem de alertas: {count_query} com params: {count_params}")
            cursor.execute(count_query, tuple(count_params))
            total_items = cursor.fetchone()[0]
            self.logger.info(f"Contagem total de alertas: {total_items}")

            query = f"{base_query_select_fields} {base_query_from} {where_clause}"
            
            if order_by and order_direction.upper() in ['ASC', 'DESC']:
                safe_order_by = "".join(c for c in order_by if c.isalnum() or c == '_')
                query += f" ORDER BY {safe_order_by} {order_direction.upper()}"
            else:
                query += " ORDER BY timestamp DESC"
            
            if per_page is not None and per_page > 0 and total_items > 0:
                offset = (page - 1) * per_page
                query += " LIMIT ? OFFSET ?"
                data_params.extend([per_page, offset])
            
            self.logger.info(f"Executando query de alertas filtrados (paginada): {query} com params: {data_params}")
            cursor.execute(query, tuple(data_params))
            alerts = cursor.fetchall()
            self.logger.info(f"Query retornou {len(alerts)} alertas.")
            return alerts, total_items
        except Exception as e:
            self.logger.error(f"Erro ao executar a query de alertas filtrados: {e}", exc_info=True)
            raise 
        finally:
            if cursor:
                cursor.close()

    def add_temp_block(self, user_id, admin_id, block_time, duration):
        """Adiciona um bloqueio temporário para um usuário."""
        try:
            expiry = block_time + duration
            self.cursor.execute("""
                INSERT INTO user_blocks (user_id, admin_id, block_type, block_time, expiry_time)
                VALUES (?, ?, 'temporary', ?, ?)
            """, (user_id, admin_id, block_time, expiry))
            self.conn.commit()
            return True
        except Exception as e:
            return False

    def add_permanent_ban(self, user_id, admin_id, ban_time, reason):
        """Adiciona um banimento permanente para um usuário."""
        try:
            self.cursor.execute("""
                INSERT INTO user_blocks (user_id, admin_id, block_type, block_time, reason)
                VALUES (?, ?, 'permanent', ?, ?)
            """, (user_id, admin_id, ban_time, reason))
            self.conn.commit()
            return True
        except Exception as e:
            return False

    def remove_all_blocks(self, user_id):
        """Remove todos os bloqueios/bans de um usuário."""
        try:
            self.cursor.execute("""
                DELETE FROM user_blocks
                WHERE user_id = ?
            """, (user_id,))
            self.conn.commit()
            return True
        except Exception as e:
            return False

    def check_user_blocks(self, user_id):
        """Verifica se um usuário está bloqueado/banido."""
        try:
            # Verifica bans permanentes
            self.cursor.execute("""
                SELECT 1 FROM user_blocks
                WHERE user_id = ? AND block_type = 'permanent'
                LIMIT 1
            """, (user_id,))
            if self.cursor.fetchone():
                return {'blocked': True, 'type': 'permanent'}

            # Verifica bloqueios temporários ativos
            current_time = get_current_utc_timestamp()
            self.cursor.execute("""
                SELECT 1 FROM user_blocks
                WHERE user_id = ? 
                AND block_type = 'temporary'
                AND expiry_time > ?
                LIMIT 1
            """, (user_id, current_time))
            if self.cursor.fetchone():
                return {'blocked': True, 'type': 'temporary'}

            return {'blocked': False, 'type': None}
        except Exception as e:
            return {'blocked': False, 'type': None, 'error': str(e)}
    def get_users_for_email_notification(self):
        """Retorna uma lista de emails de usuários que desejam receber notificações."""
        try:
            cursor = self.conn.execute('SELECT email FROM users WHERE email_notifications = 1')
            return [row[0] for row in cursor.fetchall()]
        except Exception as e:
            self.logger.error(f"Erro ao buscar emails para notificação: {e}")
            return []

    def update_user_email_notification(self, user_id, enabled):
        """Atualiza a preferência de notificação por email de um usuário."""
        try:
            with self.conn:
                self.conn.execute(
                    'UPDATE users SET email_notifications = ? WHERE id = ?',
                    (1 if enabled else 0, user_id)
                )
            return True
        except Exception as e:
            self.logger.error(f"Erro ao atualizar preferência de email para o usuário {user_id}: {e}")
            return False

    def get_all_users_paged(self, page=1, per_page=10, search=''):
        """Busca usuários de forma paginada com filtro de busca."""
        try:
            cursor = self.conn.cursor()
            offset = (page - 1) * per_page
            
            query_base = "FROM users"
            params = []
            if search:
                query_base += " WHERE username LIKE ? OR email LIKE ? OR first_name LIKE ? OR last_name LIKE ?"
                search_param = f"%{search}%"
                params.extend([search_param] * 4)

            # Contagem total
            cursor.execute(f"SELECT COUNT(*) {query_base}", params)
            total_items = cursor.fetchone()[0]

            # Busca paginada
            cursor.execute(f"""
                SELECT id, username, email, first_name, last_name, is_admin, email_notifications, created_at 
                {query_base} 
                ORDER BY created_at DESC 
                LIMIT ? OFFSET ?
            """, params + [per_page, offset])
            
            users = cursor.fetchall()
            return users, total_items
        except Exception as e:
            self.logger.error(f"Erro ao buscar usuários paginados: {e}")
            return [], 0
        finally:
            if cursor: cursor.close()

    def create_user(self, username, password, email, first_name, last_name, is_admin=0):
        try:
            cursor = self.conn.cursor()
            cursor.execute("""
                INSERT INTO users (username, password, email, first_name, last_name, is_admin, email_notifications, created_at)
                VALUES (?, ?, ?, ?, ?, ?, 0, ?)
            """, (username, password, email, first_name, last_name, is_admin, get_current_timestamp_for_storage()))
            self.conn.commit()
            self.logger.info(f"Usuário '{username}' criado com sucesso.")
            return True
        except sqlite3.IntegrityError:
            self.logger.error(f"Erro de integridade ao criar usuário '{username}' ou email '{email}'.")
            return False
        except Exception as e:
            self.logger.error(f"Erro ao criar usuário '{username}': {e}")
            return False
        finally:
            if cursor:
                cursor.close()
    def add_password_reset_token(self, user_id, token, expires_at):
        """Adiciona um token de reset de senha."""
        try:
            with self.conn:
                self.conn.execute("""
                    INSERT INTO password_resets (user_id, token, expires_at)
                    VALUES (?, ?, ?)
                """, (user_id, token, format_datetime_for_storage(expires_at)))
            return True
        except sqlite3.Error as e:
            self.logger.error(f"Erro ao salvar token de reset: {e}")
            return False

    def get_user_by_reset_token(self, token):
        """Busca usuário pelo token de reset ativo."""
        try:
            cursor = self.conn.cursor()
            now = format_datetime_for_storage(get_current_utc_timestamp())
            cursor.execute("""
                SELECT u.id, u.username, u.email 
                FROM users u
                JOIN password_resets pr ON u.id = pr.user_id
                WHERE pr.token = ? AND pr.expires_at > ? AND pr.used = 0
            """, (token, now))
            return cursor.fetchone()
        except sqlite3.Error as e:
            self.logger.error(f"Erro ao validar token de reset: {e}")
            return None

    def mark_reset_token_used(self, token):
        """Marca um token de reset como usado."""
        try:
            with self.conn:
                self.conn.execute("UPDATE password_resets SET used = 1 WHERE token = ?", (token,))
            return True
        except sqlite3.Error as e:
            self.logger.error(f"Erro ao marcar token como usado: {e}")
            return False

    def update_user_password(self, user_id, hashed_password):
        """Atualiza a senha de um usuário."""
        try:
            with self.conn:
                self.conn.execute("UPDATE users SET password = ? WHERE id = ?", (hashed_password, user_id))
            return True
        except sqlite3.Error as e:
            self.logger.error(f"Erro ao atualizar senha: {e}")
            return False

    def get_user_by_email(self, email):
        """Busca usuário pelo email."""
        try:
            cursor = self.conn.cursor()
            cursor.execute("SELECT id, username, email FROM users WHERE email = ?", (email,))
            return cursor.fetchone()
        except sqlite3.Error as e:
            self.logger.error(f"Erro ao buscar usuário por email: {e}")
            return None

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()

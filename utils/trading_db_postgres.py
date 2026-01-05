import os
import psycopg2
from psycopg2.extras import RealDictCursor
from dotenv import load_dotenv

load_dotenv()


class TradingDBPostgres:
    def __init__(self):
        self.conn = None

    def connect(self):
        if self.conn is None or self.conn.closed:
            self.conn = psycopg2.connect(
                os.getenv("DATABASE_URL"),
                cursor_factory=RealDictCursor
            )
            self.conn.autocommit = True

    def _cursor(self):
        self.connect()
        return self.conn.cursor()

    # ========= POSITIONS =========

    def get_all_positions(self, active_only=True):
        with self._cursor() as cur:
            if active_only:
                cur.execute(
                    "select * from positions where is_active = true order by created_at desc"
                )
            else:
                cur.execute(
                    "select * from positions order by created_at desc"
                )
            return cur.fetchall()

    def add_to_db(self, name, percent, cross, entry_price, tp, sl, pos_type):
        with self._cursor() as cur:
            cur.execute("""
                insert into positions
                (name, percent, cross_margin, entry_price, take_profit, stop_loss, pos_type)
                values (%s,%s,%s,%s,%s,%s,%s)
                returning id
            """, (name, percent, cross, entry_price, tp, sl, pos_type))
            return cur.fetchone()["id"]

    def update_position(self, position_id, **fields):
        keys = fields.keys()
        values = list(fields.values())

        set_clause = ", ".join(f"{k} = %s" for k in keys)

        with self._cursor() as cur:
            cur.execute(
                f"update positions set {set_clause}, updated_at = now() where id = %s",
                values + [position_id]
            )

    def delete_position(self, position_id):
        with self._cursor() as cur:
            cur.execute("delete from positions where id = %s", (position_id,))
            return True

    # ========= BOT USERS =========

    def add_user(self, user_id, username, first_name, last_name):
        with self._cursor() as cur:
            cur.execute("""
                insert into bot_users (user_id, username, first_name, last_name)
                values (%s,%s,%s,%s)
                on conflict (user_id) do update
                set username = excluded.username,
                    first_name = excluded.first_name,
                    last_name = excluded.last_name,
                    is_active = true
            """, (user_id, username, first_name, last_name))

    def get_active_users(self):
        with self._cursor() as cur:
            cur.execute(
                "select user_id from bot_users where is_active = true"
            )
            return [r["user_id"] for r in cur.fetchall()]

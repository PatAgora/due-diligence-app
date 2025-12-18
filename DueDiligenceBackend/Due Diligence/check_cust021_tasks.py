import sqlite3

DB_PATH = "scrutinise_workflow.db"


def main():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    cur = conn.cursor()

    try:
        cur.execute(
            "SELECT task_id, customer_id, status, assigned_to "
            "FROM reviews "
            "WHERE customer_id IN ('CUST021','CUST022') "
            "ORDER BY task_id"
        )
        rows = cur.fetchall()
    except Exception as e:
        print("Error querying reviews:", e)
        return
    finally:
        conn.close()

    print(f"Total tasks for CUST021/CUST022: {len(rows)}")
    for r in rows:
        print(dict(r))


if __name__ == "__main__":
    main()



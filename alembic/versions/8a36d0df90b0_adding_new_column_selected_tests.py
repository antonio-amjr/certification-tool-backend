"""Adding new column selected_tests

Revision ID: 8a36d0df90b0
Revises: 3189c039e59b
Create Date: 2023-12-04 20:15:28.319836

"""
import json

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision = "8a36d0df90b0"
down_revision = "3189c039e59b"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column(
        "testrunexecution", sa.Column("selected_tests", sa.JSON(), nullable=True)
    )

    t_testrunexecution = sa.Table(
        "testrunexecution",
        sa.MetaData(),
        sa.Column("id", sa.String(32)),
        sa.Column("selected_tests", sa.Unicode(length=1000)),
    )
    t_testsuiteexecution = sa.Table(
        "testsuiteexecution",
        sa.MetaData(),
        sa.Column("id", sa.String(32)),
        sa.Column("public_id", sa.Unicode(length=100)),
        sa.Column("collection_id", sa.Unicode(length=100)),
        sa.Column("test_run_execution_id", sa.Unicode(length=100)),
    )
    t_testcaseexecution = sa.Table(
        "testcaseexecution",
        sa.MetaData(),
        sa.Column("public_id", sa.Unicode(length=100)),
        sa.Column("test_suite_execution_id", sa.Unicode(length=100)),
    )
    connection = op.get_bind()
    run_ids = [
        r[0] for r in connection.execute(sa.select(t_testrunexecution.c.id)).all()
    ]
    for run_id in run_ids:
        selected_tests = {"collections": []}
        collections = [
            c[0]
            for c in connection.execute(
                sa.select(t_testsuiteexecution.c.collection_id)
                .where(t_testsuiteexecution.c.test_run_execution_id == run_id)
                .distinct()
            ).all()
        ]
        for collection in collections:
            selected_tests["collections"].append(
                {"public_id": collection, "test_suites": []}
            )
            suites = connection.execute(
                sa.select(
                    t_testsuiteexecution.c.id, t_testsuiteexecution.c.public_id
                ).where(
                    (t_testsuiteexecution.c.test_run_execution_id == run_id)
                    & (t_testsuiteexecution.c.collection_id == collection)
                )
            ).all()
            for suite in suites:
                cases = [
                    {"public_id": c[0], "iterations": 1}
                    for c in connection.execute(
                        sa.select(t_testcaseexecution.c.public_id).where(
                            t_testcaseexecution.c.test_suite_execution_id == suite[0]
                        )
                    ).all()
                ]
                selected_tests["collections"][-1]["test_suites"].append(
                    {"public_id": suite[1], "test_cases": cases}
                )
        connection.execute(
            t_testrunexecution.update()
            .where(t_testrunexecution.c.id == run_id)
            .values(selected_tests=json.dumps(selected_tests))
        )
    op.alter_column("testrunexecution", "selected_tests", nullable=False)


def downgrade():
    op.drop_column("testrunexecution", "selected_tests")

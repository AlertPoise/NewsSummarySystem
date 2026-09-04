"""数据库模型测试骨架。"""

from app.models import Favorite, Feedback, ModelEvaluation, NewsArticle


def test_database_models_are_available() -> None:
    """验证已冻结 ORM 模型可被导入。"""
    assert NewsArticle.__tablename__ == "news_articles"
    assert Favorite.__tablename__ == "favorites"
    assert Feedback.__tablename__ == "feedback"
    assert ModelEvaluation.__tablename__ == "model_evaluations"


# TODO(A-阶段3)：在隔离 MySQL 测试库中验证表字段、外键和收藏及反馈唯一约束；输入为 sql/create_database.sql，输出为一致性测试结果，必须遵守 docs/DATABASE.md。

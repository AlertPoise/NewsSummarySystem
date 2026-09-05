"""正式模型性能测试入口。"""


def main() -> None:
    """统计已加载模型的平均和 P95 摘要耗时。"""
    # TODO(B-阶段2)：在 C2-11/C2-14 提供的完整正式 Pipeline 上，按 batch_size=1、模型已加载和 GPU 已预热的规则测试 SummaryPipeline.generate(article)；输入为真实测试新闻，输出为平均、P95 与性能达标率，必须遵守 docs/ARCHITECTURE.md 与 docs/REQUIREMENTS.md。
    raise NotImplementedError("阶段2由B进行真实性能测试")


if __name__ == "__main__":
    main()

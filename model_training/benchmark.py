"""正式模型性能测试入口。"""


def main() -> None:
    """统计已加载模型的平均和 P95 摘要耗时。"""
    # TODO(B-阶段2)：按 batch size 为 1、模型加载和 GPU 预热完成后的规则测试 SummaryPipeline.generate(article)；输入为真实测试新闻，输出为平均与 P95 毫秒数，必须遵守 docs/TEST_PLAN.md 的小于 1.5 秒验收标准。
    raise NotImplementedError("阶段2由B进行真实性能测试")


if __name__ == "__main__":
    main()

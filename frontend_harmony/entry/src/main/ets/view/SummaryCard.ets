/**
 * AI 摘要卡片组件（E4-11/E4-15 配套）。
 * 数值属性一律 @Prop：与页面级 @State 镜像建立单向同步，父侧变化会推送并触发
 * 本组件重绘。V1 状态管理下普通成员变量虽会被父组件重赋值，但不触发子组件
 * 重绘——这正是此前“摘要已完成、轮询已返回 200，卡片仍停在生成中/未生成”的根因。
 * 回调仍为普通属性（无需刷新语义）。所有文案状态均由服务端字段驱动，不伪造结果。
 *
 * 取值约定（避免 @Prop 联合类型兼容性问题，用哨兵值表达“无”）：
 * - summaryText 空串 = 尚无摘要正文；summaryTimeMs < 0 = 耗时未知。
 */

@Component
export struct SummaryCard {
  /** 摘要状态机状态：pending/processing/completed/failed。 */
  @Prop summaryStatus: string = 'pending';

  /** 最终摘要正文（completed 且非空时展示）。 */
  @Prop summaryText: string = '';

  /** 摘要生成耗时毫秒（<0 表示未知）。 */
  @Prop summaryTimeMs: number = -1;

  /** 当前用户反馈：true=有帮助，false=没帮助，null=未反馈。 */
  @Prop feedback: boolean | null = null;

  /** 摘要生成请求或状态轮询进行中。 */
  @Prop busy: boolean = false;

  /** 反馈提交进行中。 */
  @Prop feedbackBusy: boolean = false;

  /** 生成/重试摘要回调。 */
  onGenerate: () => void = () => {
  };

  /** 反馈回调（true=有帮助，false=没帮助）。 */
  onFeedback: (helpful: boolean) => void = (helpful: boolean) => {
  };

  /** 手动刷新状态回调。 */
  onRefresh: () => void = () => {
  };

  build() {
    Column({ space: 10 }) {
      Row() {
        Text('AI 摘要')
          .fontSize(15)
          .fontWeight(FontWeight.Medium)
          .fontColor('#1C1C1E')
        Text('正式摘要流水线生成')
          .fontSize(10)
          .fontColor('#B0B4BC')
          .margin({ left: 8 })
        Blank()
        if (!this.busy && this.summaryStatus !== 'completed') {
          Text('刷新状态')
            .fontSize(12)
            .fontColor('#2B6BFF')
            .onClick(() => {
              this.onRefresh();
            })
        }
      }
      .width('100%')
      .alignItems(VerticalAlign.Center)

      // 处理中：生成请求或轮询期间
      if (this.busy) {
        Row({ space: 8 }) {
          LoadingProgress()
            .width(18)
            .height(18)
            .color('#2B6BFF')
          Text('摘要生成中（首次约需 10~30 秒加载模型）…')
            .fontSize(14)
            .fontColor('#5A5F6A')
        }
        .width('100%')
        .justifyContent(FlexAlign.Start)
        .alignItems(VerticalAlign.Center)
        .padding({ top: 6, bottom: 6 })
      } else if (this.summaryStatus === 'completed' && this.summaryText.length > 0) {
        // 已生成：摘要正文 + 耗时 + 反馈
        Text(this.summaryText)
          .fontSize(15)
          .lineHeight(24)
          .fontColor('#1C1C1E')
          .width('100%')
        if (this.summaryTimeMs >= 0) {
          Text(`模型推理耗时：${this.summaryTimeMs} ms（不含加载/排队）`)
            .fontSize(11)
            .fontColor('#B0B4BC')
            .width('100%')
        }
        Row({ space: 10 }) {
          Text('摘要是否对你有帮助？')
            .fontSize(12)
            .fontColor('#8A8F99')
          Text('有帮助')
            .fontSize(12)
            .fontColor(this.feedback === true ? Color.White : '#2BA471')
            .padding({ left: 10, right: 10, top: 4, bottom: 4 })
            .borderRadius(12)
            .backgroundColor(this.feedback === true ? '#2BA471' : '#E8F6EF')
            .onClick(() => {
              if (!this.feedbackBusy) {
                this.onFeedback(true);
              }
            })
          Text('没帮助')
            .fontSize(12)
            .fontColor(this.feedback === false ? Color.White : '#E5484D')
            .padding({ left: 10, right: 10, top: 4, bottom: 4 })
            .borderRadius(12)
            .backgroundColor(this.feedback === false ? '#E5484D' : '#FDEBEC')
            .onClick(() => {
              if (!this.feedbackBusy) {
                this.onFeedback(false);
              }
            })
        }
        .width('100%')
        .alignItems(VerticalAlign.Center)
      } else if (this.summaryStatus === 'failed') {
        // 生成失败：提供重试
        Column({ space: 8 }) {
          Text('摘要生成失败')
            .fontSize(14)
            .fontColor('#E5484D')
          Text('可点击下方按钮重新发起生成任务')
            .fontSize(12)
            .fontColor('#8A8F99')
        }
        .width('100%')
        .alignItems(HorizontalAlign.Start)
        Text('重试生成摘要')
          .fontSize(13)
          .fontColor(Color.White)
          .padding({ left: 14, right: 14, top: 7, bottom: 7 })
          .borderRadius(15)
          .backgroundColor('#2B6BFF')
          .onClick(() => {
            this.onGenerate();
          })
      } else if (this.summaryStatus === 'processing') {
        // 自动刷新已停止但仍处理中：提示手动刷新状态
        Text('摘要仍在服务端处理中，请稍后点击上方“刷新状态”查看结果')
          .fontSize(14)
          .fontColor('#5A5F6A')
          .lineHeight(22)
          .width('100%')
      } else {
        // pending 或其他状态：发起生成入口
        Column({ space: 8 }) {
          Text('摘要尚未生成')
            .fontSize(14)
            .fontColor('#5A5F6A')
          Text('点击下方按钮向服务端发起摘要任务，生成完成后自动刷新展示')
            .fontSize(12)
            .fontColor('#B0B4BC')
        }
        .width('100%')
        .alignItems(HorizontalAlign.Start)
        Text('生成摘要')
          .fontSize(13)
          .fontColor(Color.White)
          .padding({ left: 14, right: 14, top: 7, bottom: 7 })
          .borderRadius(15)
          .backgroundColor('#2B6BFF')
          .onClick(() => {
            this.onGenerate();
          })
      }
    }
    .width('100%')
    .padding(14)
    .backgroundColor('#FFFFFF')
    .borderRadius(12)
    .alignItems(HorizontalAlign.Start)
  }
}

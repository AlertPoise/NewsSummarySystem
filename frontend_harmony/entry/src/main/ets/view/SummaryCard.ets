/**
 * AI 摘要卡片组件（E4-11/E4-15 配套）。
 * 依据新闻详情中的摘要状态机（pending/processing/completed/failed）渲染对应区块：
 * - completed：展示最终摘要、生成耗时与反馈（有帮助/没帮助，可重复更新）；
 * - processing / 生成请求或轮询中：展示处理中文案；
 * - pending：提供“生成摘要”入口；failed：提供“重试”入口。
 * 所有文案状态均由服务端字段驱动，客户端不伪造摘要结果。
 */

import { NewsDetail } from '../model/News';

@Component
export struct SummaryCard {
  /** 新闻详情（含 summary_status/summary/summary_time_ms/feedback）。 */
  news: NewsDetail = new NewsDetail();

  /** 摘要生成请求或状态轮询进行中。 */
  busy: boolean = false;

  /** 反馈提交进行中。 */
  feedbackBusy: boolean = false;

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
        if (!this.busy && this.news.summary_status !== 'completed') {
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
          Text('摘要正在生成中，请稍候…')
            .fontSize(14)
            .fontColor('#5A5F6A')
        }
        .width('100%')
        .justifyContent(FlexAlign.Start)
        .alignItems(VerticalAlign.Center)
        .padding({ top: 6, bottom: 6 })
      } else if (this.news.summary_status === 'completed' && this.news.summary !== null) {
        // 已生成：摘要正文 + 耗时 + 反馈
        Text(this.news.summary)
          .fontSize(15)
          .lineHeight(24)
          .fontColor('#1C1C1E')
          .width('100%')
        if (this.news.summary_time_ms !== null) {
          Text(`生成耗时：${this.news.summary_time_ms} ms`)
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
            .fontColor(this.news.feedback === true ? Color.White : '#2BA471')
            .padding({ left: 10, right: 10, top: 4, bottom: 4 })
            .borderRadius(12)
            .backgroundColor(this.news.feedback === true ? '#2BA471' : '#E8F6EF')
            .onClick(() => {
              if (!this.feedbackBusy) {
                this.onFeedback(true);
              }
            })
          Text('没帮助')
            .fontSize(12)
            .fontColor(this.news.feedback === false ? Color.White : '#E5484D')
            .padding({ left: 10, right: 10, top: 4, bottom: 4 })
            .borderRadius(12)
            .backgroundColor(this.news.feedback === false ? '#E5484D' : '#FDEBEC')
            .onClick(() => {
              if (!this.feedbackBusy) {
                this.onFeedback(false);
              }
            })
        }
        .width('100%')
        .alignItems(VerticalAlign.Center)
      } else if (this.news.summary_status === 'failed') {
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
      } else if (this.news.summary_status === 'processing') {
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

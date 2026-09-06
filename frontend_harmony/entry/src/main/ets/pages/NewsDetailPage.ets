/**
 * 新闻详情页（E4-10~E4-12、E4-13、E4-15 配套）。
 * - 展示标题、来源、发布时间、AI 摘要（按状态机）、全文；
 * - 收藏/取消收藏调用收藏 API（幂等语义，界面以响应为准）；
 * - 摘要反馈可重复更新；摘要生成中有限轮询详情接口，最终状态来自服务端；
 * - 支持整页 Loading/Empty/Error 与操作错误提示条。
 */

import { BusinessError } from '@kit.BasicServicesKit';
import { common } from '@kit.AbilityKit';
import { NewsDetailViewModel } from '../viewmodel/NewsDetailViewModel';
import { NewsDetail } from '../model/News';
import { jsonNumber, jsonObject } from '../common/JsonUtil';
import { categoryColor, formatIsoTime } from '../common/Formatters';
import { LoadingView } from '../view/LoadingView';
import { ErrorView } from '../view/ErrorView';
import { SummaryCard } from '../view/SummaryCard';

@Entry
@Component
struct NewsDetailPage {
  @State vm: NewsDetailViewModel = new NewsDetailViewModel();

  // ---- 镜像状态：把详情对象中“运行期会变化”的字段镜像为页面级 @State ----
  // V1 状态下对象深层字段/整体替换存在刷新盲区，镜像简单字段保证点击后立即重绘。
  /** 当前是否已收藏（按钮即时反馈）。 */
  @State favOn: boolean = false;
  /** 收藏请求进行中（按钮半透明防连点）。 */
  @State favBusyOn: boolean = false;
  /** 摘要状态机：pending/processing/completed/failed。 */
  @State sumStatus: string = 'pending';
  /** 摘要正文（completed 后非空）。 */
  @State sumText: string | null = null;
  /** 生成耗时毫秒。 */
  @State sumTimeMs: number | null = null;
  /** 用户反馈（true/false/null）。 */
  @State sumFeedback: boolean | null = null;
  /** 反馈提交进行中。 */
  @State fbBusyOn: boolean = false;

  aboutToAppear(): void {
    this.vm.onDetailChanged = (): void => {
      this.syncFromVm();
    };
    this.vm.attach(getContext(this) as common.UIAbilityContext);
    const params: Record<string, Object> | null = jsonObject(this.getUIContext().getRouter().getParams());
    if (params === null) {
      this.vm.loading = false;
      this.vm.errorMessage = '缺少新闻参数，无法打开详情';
      return;
    }
    const newsIdValue: number | null = jsonNumber(params, 'newsId');
    if (newsIdValue === null) {
      this.vm.loading = false;
      this.vm.errorMessage = '新闻参数无效，无法打开详情';
      return;
    }
    this.syncFromVm();
    this.vm.load(newsIdValue);
  }

  /** 从 ViewModel 同步镜像字段（detail 每次替换后由回调触发）。 */
  private syncFromVm(): void {
    const d: NewsDetail | null = this.vm.detail;
    if (d === null) {
      this.favOn = false;
      this.sumStatus = 'pending';
      this.sumText = null;
      this.sumTimeMs = null;
      this.sumFeedback = null;
    } else {
      this.favOn = d.is_favorite;
      this.sumStatus = d.summary_status;
      this.sumText = d.summary;
      this.sumTimeMs = d.summary_time_ms;
      this.sumFeedback = d.feedback;
    }
    this.favBusyOn = this.vm.favoriteBusy;
    this.fbBusyOn = this.vm.feedbackBusy;
  }

  aboutToDisappear(): void {
    this.vm.destroy();
  }

  build() {
    Column() {
      // 顶部操作栏：返回 / 标题 / 刷新
      Row() {
        Text('返回')
          .fontSize(14)
          .fontColor('#2B6BFF')
          .onClick(() => {
            this.goBack();
          })
        Blank()
        Text('新闻详情')
          .fontSize(16)
          .fontWeight(FontWeight.Medium)
          .fontColor('#1C1C1E')
        Blank()
        if (this.vm.refreshingDetail) {
          LoadingProgress()
            .width(16)
            .height(16)
            .color('#2B6BFF')
        } else {
          Text('刷新')
            .fontSize(14)
            .fontColor('#2B6BFF')
            .onClick(() => {
              this.vm.refreshDetail();
            })
        }
      }
      .width('100%')
      .padding({ left: 12, right: 12, top: 8, bottom: 8 })

      // 摘要任务提示条（提交后仍处理中/轮询超时未完成等温和提示）
      if (this.vm.summaryNotice.length > 0) {
        Row({ space: 6 }) {
          Text('⏳')
            .fontSize(12)
          Text(this.vm.summaryNotice)
            .fontSize(12)
            .fontColor('#2B6BFF')
            .maxLines(2)
            .layoutWeight(1)
        }
        .width('100%')
        .padding({ left: 12, right: 12, top: 5, bottom: 5 })
        .backgroundColor('#E8F1FF')
      }

      // 操作错误提示条（收藏/反馈/摘要请求失败）
      if (this.vm.opError.length > 0) {
        Row({ space: 8 }) {
          Text(this.vm.opError)
            .fontSize(12)
            .fontColor('#E5484D')
            .maxLines(1)
            .textOverflow({ overflow: TextOverflow.Ellipsis })
            .layoutWeight(1)
          Text('×')
            .fontSize(14)
            .fontColor('#E5484D')
            .onClick(() => {
              this.vm.clearOpError();
            })
        }
        .width('100%')
        .padding({ left: 12, right: 12, top: 4, bottom: 4 })
        .backgroundColor('#FDEBEC')
      }

      if (this.vm.detail === null) {
        Column() {
          if (this.vm.loading) {
            LoadingView({ hint: '正在加载新闻详情…' })
          } else {
            ErrorView({
              message: this.vm.errorMessage.length > 0 ? this.vm.errorMessage : '加载失败，请稍后重试',
              onRetry: (): void => {
                this.vm.retry();
              }
            })
          }
        }
        .layoutWeight(1)
        .width('100%')
      } else {
        Column() {
          Scroll() {
            this.detailContent(this.vm.detail)
          }
          .layoutWeight(1)
          .width('100%')
          .scrollBar(BarState.Off)
          .align(Alignment.Top)
          .backgroundColor('#F5F6FA')
          .padding({ bottom: 8 })

          this.favoriteBar(this.vm.detail)
        }
        .layoutWeight(1)
        .width('100%')
      }
    }
    .width('100%')
    .height('100%')
    .backgroundColor('#F5F6FA')
  }

  /** 详情内容区：标题、元信息、AI 摘要卡片、全文。 */
  @Builder
  detailContent(detail: NewsDetail | null) {
    if (detail !== null) {
      Column({ space: 12 }) {
      Text(detail.title)
        .fontSize(21)
        .fontWeight(FontWeight.Bold)
        .fontColor('#1C1C1E')
        .lineHeight(30)
        .width('100%')

      Row({ space: 8 }) {
        Text(detail.category)
          .fontSize(11)
          .fontColor(Color.White)
          .padding({ left: 6, right: 6, top: 2, bottom: 2 })
          .borderRadius(4)
          .backgroundColor(categoryColor(detail.category))
        Text(detail.source)
          .fontSize(12)
          .fontColor('#8A8F99')
        Text(formatIsoTime(detail.publish_time))
          .fontSize(12)
          .fontColor('#8A8F99')
      }
      .width('100%')
      .alignItems(VerticalAlign.Center)

      if (detail.source_url.length > 0) {
        Text(`原文来源：${detail.source_url}`)
          .fontSize(11)
          .fontColor('#B0B4BC')
          .maxLines(1)
          .textOverflow({ overflow: TextOverflow.Ellipsis })
          .width('100%')
      }

      // AI 摘要卡片：由页面镜像状态（@State）驱动，保证运行期状态变化即时重绘
      SummaryCard({
        summaryStatus: this.sumStatus,
        summaryText: this.sumText ?? '',
        summaryTimeMs: this.sumTimeMs ?? -1,
        feedback: this.sumFeedback,
        busy: this.vm.isSummaryInProgress(),
        feedbackBusy: this.fbBusyOn,
        onGenerate: (): void => {
          this.vm.requestSummary();
        },
        onFeedback: (helpful: boolean): void => {
          this.vm.submitFeedback(helpful);
        },
        onRefresh: (): void => {
          this.vm.refreshDetail();
        }
      })

      // 全文
      Column({ space: 8 }) {
        Text('新闻全文')
          .fontSize(15)
          .fontWeight(FontWeight.Medium)
          .fontColor('#1C1C1E')
          .width('100%')
        Text(detail.content)
          .fontSize(15)
          .lineHeight(26)
          .fontColor('#2A2A2E')
          .width('100%')
      }
      .width('100%')
      .padding(14)
      .backgroundColor('#FFFFFF')
      .borderRadius(12)
      .alignItems(HorizontalAlign.Start)
      }
      .width('100%')
      .padding({ left: 12, right: 12, top: 6 })
      .alignItems(HorizontalAlign.Start)
    }
  }

  /** 底部收藏操作条：镜像状态（@State favOn）驱动，点击立即翻转，失败由 VM 回滚。 */
  @Builder
  favoriteBar(detail: NewsDetail | null) {
    if (detail !== null) {
      Row() {
      Row({ space: 8 }) {
        Text(this.favOn ? '♥' : '♡')
          .fontSize(20)
          .fontColor(this.favOn ? '#E5484D' : Color.White)
          .fontWeight(FontWeight.Bold)
        Text(this.favOn ? '已收藏 · 点击取消' : '收藏本篇新闻')
          .fontSize(14)
          .fontColor(this.favOn ? '#E5484D' : Color.White)
          .fontWeight(FontWeight.Medium)
      }
      .width('100%')
      .height(46)
      .borderRadius(23)
      .justifyContent(FlexAlign.Center)
      .backgroundColor(this.favOn ? '#FDEBEC' : '#2B6BFF')
      .opacity(this.favBusyOn ? 0.55 : 1)
      .onClick(() => {
        this.vm.toggleFavorite();
      })
      }
      .width('100%')
      .padding({ left: 12, right: 12, top: 6, bottom: 14 })
      .backgroundColor('#FFFFFF')
    }
  }

  /** 返回上一页。 */
  private goBack(): void {
    this.getUIContext().getRouter().back();
  }
}

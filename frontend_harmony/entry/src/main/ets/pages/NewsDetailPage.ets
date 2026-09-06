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

  aboutToAppear(): void {
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
    this.vm.load(newsIdValue);
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
        Text('刷新')
          .fontSize(14)
          .fontColor('#2B6BFF')
          .onClick(() => {
            this.vm.refreshDetail();
          })
      }
      .width('100%')
      .padding({ left: 12, right: 12, top: 8, bottom: 8 })

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

      // AI 摘要卡片：状态机驱动展示与操作
      SummaryCard({
        news: detail,
        busy: this.vm.isSummaryInProgress(),
        feedbackBusy: this.vm.feedbackBusy,
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

  /** 底部收藏操作条：状态以服务端响应为准。 */
  @Builder
  favoriteBar(detail: NewsDetail | null) {
    if (detail !== null) {
      Row() {
      Row({ space: 6 }) {
        Text(detail.is_favorite ? '已收藏，点击取消' : '收藏本篇新闻')
          .fontSize(14)
          .fontColor(detail.is_favorite ? '#E5484D' : Color.White)
          .fontWeight(FontWeight.Medium)
      }
      .width('100%')
      .height(46)
      .borderRadius(23)
      .justifyContent(FlexAlign.Center)
      .backgroundColor(detail.is_favorite ? '#FDEBEC' : '#2B6BFF')
      .opacity(this.vm.favoriteBusy ? 0.5 : 1)
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

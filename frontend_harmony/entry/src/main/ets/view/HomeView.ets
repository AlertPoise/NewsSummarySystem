/**
 * 首页视图（E4-06~E4-09 配套）。
 * - 分类：分类来自 GET /api/categories（六类固定顺序），“全部”为客户端本地筛选入口；
 * - 列表：GET /api/news 卡片列表（不含 content），点击进入详情；
 * - 分页：触底加载下一页（page_size=20，遵守 1~50 契约）；
 * - 刷新：下拉刷新与顶部“刷新”按钮复位到第一页；
 * - 状态：首屏加载/空态/错误态/加载更多失败均独立展示。
 */

import { BusinessError } from '@kit.BasicServicesKit';
import { NewsViewModel } from '../viewmodel/NewsViewModel';
import { NewsItem } from '../model/News';
import { LoadingView } from './LoadingView';
import { EmptyView } from './EmptyView';
import { ErrorView } from './ErrorView';
import { NewsCard } from './NewsCard';

@Component
export struct HomeView {
  @State vm: NewsViewModel = new NewsViewModel();

  aboutToAppear(): void {
    this.vm.loadInitial();
  }

  build() {
    Column() {
      // 顶部：标题 + 刷新按钮
      Row() {
        Text('新闻资讯')
          .fontSize(20)
          .fontWeight(FontWeight.Bold)
          .fontColor('#1C1C1E')
        Blank()
        Text('刷新')
          .fontSize(14)
          .fontColor('#2B6BFF')
          .onClick(() => {
            this.vm.refresh();
          })
      }
      .width('100%')
      .padding({ left: 12, right: 12, top: 10, bottom: 6 })

      // 分类行：固定六类来自服务端
      Scroll() {
        Row({ space: 8 }) {
          this.categoryChip('')
          ForEach(this.vm.categories, (category: string) => {
            this.categoryChip(category)
          }, (category: string) => category)
        }
        .padding({ left: 12, right: 12, top: 2, bottom: 6 })
      }
      .width('100%')
      .scrollable(ScrollDirection.Horizontal)
      .scrollBar(BarState.Off)
      .height(40)

      // 有数据时的错误提示条（刷新失败等），点击重试
      if (this.vm.errorMessage.length > 0 && this.vm.newsList.length > 0) {
        Row({ space: 8 }) {
          Text(this.vm.errorMessage)
            .fontSize(12)
            .fontColor('#E5484D')
            .maxLines(1)
            .textOverflow({ overflow: TextOverflow.Ellipsis })
            .layoutWeight(1)
          Text('重试')
            .fontSize(12)
            .fontColor('#2B6BFF')
            .onClick(() => {
              this.vm.refresh();
            })
        }
        .width('100%')
        .padding({ left: 12, right: 12, top: 4, bottom: 4 })
        .backgroundColor('#FDEBEC')
      }

      // 主内容区
      Column() {
        if (this.vm.errorMessage.length > 0 && this.vm.newsList.length === 0) {
          ErrorView({ message: this.vm.errorMessage, onRetry: (): void => {
            this.vm.loadInitial();
          } })
        } else if (this.vm.newsList.length === 0 && this.vm.loading) {
          LoadingView({ hint: '正在加载新闻…' })
        } else if (this.vm.newsList.length === 0) {
          EmptyView({ hint: '暂无新闻', subHint: '下拉或点击“刷新”重新获取' })
        } else {
          this.newsListArea()
        }
      }
      .layoutWeight(1)
      .width('100%')
    }
    .width('100%')
    .height('100%')
    .backgroundColor('#F5F6FA')
  }

  /** 分类筛选条目（空串表示全部）。 */
  @Builder
  categoryChip(category: string) {
    Text(category.length === 0 ? '全部' : category)
      .fontSize(13)
      .fontColor(this.vm.selectedCategory === category ? Color.White : '#5A5F6A')
      .padding({ left: 14, right: 14, top: 6, bottom: 6 })
      .borderRadius(15)
      .backgroundColor(this.vm.selectedCategory === category ? '#2B6BFF' : '#FFFFFF')
      .onClick(() => {
        this.vm.switchCategory(category);
      })
  }

  /** 新闻列表区：下拉刷新 + 触底分页 + 底部状态。 */
  @Builder
  newsListArea() {
    Refresh({ refreshing: this.vm.refreshing }) {
      List({ space: 10 }) {
        ForEach(this.vm.newsList, (item: NewsItem) => {
          ListItem() {
            NewsCard({ news: item, onItemClick: (newsId: number): void => {
              this.openDetail(newsId);
            } })
          }
        }, (item: NewsItem) => `${item.id}-${item.summary_status}`)

        if (this.vm.hasMore) {
          ListItem() {
            Row({ space: 8 }) {
              if (this.vm.loadingMore) {
                LoadingProgress()
                  .width(16)
                  .height(16)
                  .color('#2B6BFF')
                Text('加载中…')
                  .fontSize(12)
                  .fontColor('#8A8F99')
              } else if (this.vm.moreFailed) {
                Text('加载失败，点击重试')
                  .fontSize(12)
                  .fontColor('#E5484D')
                  .onClick(() => {
                    this.vm.loadMore();
                  })
              } else {
                Text('上拉加载更多')
                  .fontSize(12)
                  .fontColor('#B0B4BC')
              }
            }
            .width('100%')
            .height(44)
            .justifyContent(FlexAlign.Center)
          }
        } else {
          ListItem() {
            Text('没有更多了')
              .fontSize(12)
              .fontColor('#B0B4BC')
              .width('100%')
              .height(44)
              .textAlign(TextAlign.Center)
          }
        }
      }
      .width('100%')
      .height('100%')
      .padding({ left: 12, right: 12, top: 4, bottom: 4 })
      .scrollBar(BarState.Off)
      .onReachEnd(() => {
        this.vm.loadMore();
      })
    }
    .width('100%')
    .height('100%')
    .onRefreshing(() => {
      this.vm.refresh();
    })
  }

  /** 跳转新闻详情页（携带 newsId 参数）。 */
  private openDetail(newsId: number): void {
    const params: Record<string, Object> = { 'newsId': newsId };
    this.getUIContext().getRouter()
      .pushUrl({ url: 'pages/NewsDetailPage', params: params })
      .catch((err: BusinessError) => {
        console.error(`跳转新闻详情失败：${err.message}`);
      });
  }
}

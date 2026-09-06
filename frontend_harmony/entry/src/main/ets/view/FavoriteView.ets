/**
 * 收藏视图（E4-13/E4-14 配套）。
 * GET /api/favorites 仅返回当前 X-Client-ID 的收藏；
 * 收藏变化由详情页写 AppStorage('favoritesDirty') 版本号，本视图监听后自动重拉；
 * 同时提供下拉刷新与空态/错误态。
 */

import { BusinessError } from '@kit.BasicServicesKit';
import { common } from '@kit.AbilityKit';
import { FavoriteViewModel } from '../viewmodel/FavoriteViewModel';
import { NewsItem } from '../model/News';
import { LoadingView } from './LoadingView';
import { EmptyView } from './EmptyView';
import { ErrorView } from './ErrorView';
import { NewsCard } from './NewsCard';

@Component
export struct FavoriteView {
  @State vm: FavoriteViewModel = new FavoriteViewModel();

  /** 收藏脏标记：详情页收藏变化后递增，触发本视图刷新。 */
  @StorageLink('favoritesDirty') @Watch('onFavoritesDirty') favoritesDirty: number = 0;

  aboutToAppear(): void {
    this.vm.attach(getContext(this) as common.UIAbilityContext);
    this.vm.reload();
  }

  /** 收藏数据在详情页被修改后的自动刷新。 */
  onFavoritesDirty(): void {
    this.vm.reload();
  }

  build() {
    Column() {
      Row() {
        Text('我的收藏')
          .fontSize(20)
          .fontWeight(FontWeight.Bold)
          .fontColor('#1C1C1E')
        if (this.vm.favorites.length > 0) {
          Text(`${this.vm.favorites.length} 条`)
            .fontSize(12)
            .fontColor('#8A8F99')
            .margin({ left: 8 })
        }
        Blank()
        Text('刷新')
          .fontSize(14)
          .fontColor('#2B6BFF')
          .onClick(() => {
            this.vm.reload();
          })
      }
      .width('100%')
      .padding({ left: 12, right: 12, top: 10, bottom: 6 })

      if (this.vm.errorMessage.length > 0 && this.vm.favorites.length > 0) {
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
              this.vm.reload();
            })
        }
        .width('100%')
        .padding({ left: 12, right: 12, top: 4, bottom: 4 })
        .backgroundColor('#FDEBEC')
      }

      Column() {
        if (this.vm.errorMessage.length > 0 && this.vm.favorites.length === 0) {
          ErrorView({ message: this.vm.errorMessage, onRetry: (): void => {
            this.vm.reload();
          } })
        } else if (this.vm.favorites.length === 0 && this.vm.loading) {
          LoadingView({ hint: '正在加载收藏…' })
        } else if (this.vm.favorites.length === 0) {
          EmptyView({ hint: '暂无收藏', subHint: '在新闻详情页点击“收藏”后即可在此查看' })
        } else {
          this.favoriteListArea()
        }
      }
      .layoutWeight(1)
      .width('100%')
    }
    .width('100%')
    .height('100%')
    .backgroundColor('#F5F6FA')
  }

  /** 收藏列表：下拉刷新。 */
  @Builder
  favoriteListArea() {
    Refresh({ refreshing: this.vm.refreshing }) {
      List({ space: 10 }) {
        ForEach(this.vm.favorites, (item: NewsItem) => {
          ListItem() {
            NewsCard({ news: item, onItemClick: (newsId: number): void => {
              this.openDetail(newsId);
            } })
          }
        }, (item: NewsItem) => item.id.toString())
      }
      .width('100%')
      .height('100%')
      .padding({ left: 12, right: 12, top: 4, bottom: 4 })
      .scrollBar(BarState.Off)
    }
    .width('100%')
    .height('100%')
    .onRefreshing(() => {
      this.vm.reload();
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

/**
 * 主导航框架（E4-05）：底部三个 Tab 入口——首页（HomeView）/ 收藏（FavoriteView）/ 关于（AboutView）。
 * Tab 内容由各视图自持 ViewModel，经由 HttpClient 调用后端 REST API。
 */

import { HomeView } from '../view/HomeView';
import { FavoriteView } from '../view/FavoriteView';
import { AboutView } from '../view/AboutView';

@Component
export struct MainPage {
  /** 当前 Tab 索引：0=首页、1=收藏、2=关于。 */
  @State currentTab: number = 0;

  build() {
    Tabs({ barPosition: BarPosition.End, index: this.currentTab }) {
      TabContent() {
        HomeView()
          .width('100%')
          .height('100%')
      }
      .tabBar(this.tabItem(0, '首页'))

      TabContent() {
        FavoriteView()
          .width('100%')
          .height('100%')
      }
      .tabBar(this.tabItem(1, '收藏'))

      TabContent() {
        AboutView()
          .width('100%')
          .height('100%')
      }
      .tabBar(this.tabItem(2, '关于'))
    }
    .width('100%')
    .height('100%')
    .scrollable(false)
    .barBackgroundColor('#FFFFFF')
    .onChange((index: number) => {
      this.currentTab = index;
    })
  }

  /** 底部 Tab 条目标签。 */
  @Builder
  tabItem(index: number, label: string) {
    Column() {
      Text(label)
        .fontSize(this.currentTab === index ? 16 : 14)
        .fontWeight(this.currentTab === index ? FontWeight.Bold : FontWeight.Normal)
        .fontColor(this.currentTab === index ? '#2B6BFF' : '#8A8F99')
    }
    .width('100%')
    .height('100%')
    .justifyContent(FlexAlign.Center)
  }
}

/**
 * 新闻卡片组件（E4-07 配套）：首页/收藏列表共用。
 * 仅展示列表契约字段，绝不展示 content；摘要为空时按状态显示标记。
 */

import { NewsItem } from '../model/News';
import { categoryColor, formatIsoTime, summaryStatusColor, summaryStatusLabel } from '../common/Formatters';

@Component
export struct NewsCard {
  /** 新闻列表项数据。 */
  news: NewsItem = new NewsItem();

  /** 点击回调（参数为新闻 ID）。 */
  onItemClick: (newsId: number) => void = (newsId: number) => {
  };

  build() {
    Column({ space: 6 }) {
      Text(this.news.title)
        .fontSize(16)
        .fontWeight(FontWeight.Medium)
        .fontColor('#1C1C1E')
        .maxLines(2)
        .textOverflow({ overflow: TextOverflow.Ellipsis })
        .width('100%')
      if (this.news.summary !== null && this.news.summary !== '') {
        Text(this.news.summary)
          .fontSize(14)
          .fontColor('#5A5F6A')
          .maxLines(2)
          .textOverflow({ overflow: TextOverflow.Ellipsis })
          .width('100%')
      }
      Row({ space: 8 }) {
        Text(this.news.category)
          .fontSize(11)
          .fontColor(Color.White)
          .padding({ left: 6, right: 6, top: 2, bottom: 2 })
          .borderRadius(4)
          .backgroundColor(categoryColor(this.news.category))
        Text(this.news.source)
          .fontSize(12)
          .fontColor('#8A8F99')
        Text(formatIsoTime(this.news.publish_time))
          .fontSize(12)
          .fontColor('#8A8F99')
        Blank()
        Text(summaryStatusLabel(this.news.summary_status))
          .fontSize(11)
          .fontColor(summaryStatusColor(this.news.summary_status))
      }
      .width('100%')
      .alignItems(VerticalAlign.Center)
    }
    .width('100%')
    .padding(14)
    .backgroundColor('#FFFFFF')
    .borderRadius(12)
    .alignItems(HorizontalAlign.Start)
    .onClick(() => {
      this.onItemClick(this.news.id);
    })
  }
}

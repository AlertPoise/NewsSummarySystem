/**
 * 关于/模型指标视图（E4-16/E4-05 配套）。
 * 指标全部来自 GET /api/model/metrics（B 交付的 CNewSum test 正式评价），不硬编码任何数值；
 * 服务端明确返回“暂无正式评价记录”（404/1002）时展示空态并提示等待 B 交付。
 */

import { MetricsViewModel } from '../viewmodel/MetricsViewModel';
import { MetricsData } from '../model/News';
import { ApiConfig } from '../common/ApiConfig';
import { LoadingView } from './LoadingView';
import { EmptyView } from './EmptyView';
import { ErrorView } from './ErrorView';

@Component
export struct AboutView {
  @State vm: MetricsViewModel = new MetricsViewModel();

  aboutToAppear(): void {
    this.vm.load();
  }

  build() {
    Column() {
      Row() {
        Text('模型指标')
          .fontSize(20)
          .fontWeight(FontWeight.Bold)
          .fontColor('#1C1C1E')
        Blank()
        Text('刷新')
          .fontSize(14)
          .fontColor('#2B6BFF')
          .onClick(() => {
            this.vm.load();
          })
      }
      .width('100%')
      .padding({ left: 12, right: 12, top: 10, bottom: 6 })

      Scroll() {
        Column({ space: 12 }) {
          // 指标卡片区（加载/错误/空态/数据 四态）
          if (this.vm.loading && this.vm.metrics === null) {
            Column() {
              LoadingView({ hint: '正在加载模型指标…' })
            }
            .width('100%')
            .height(220)
          } else if (this.vm.errorMessage.length > 0) {
            Column() {
              ErrorView({ message: this.vm.errorMessage, onRetry: (): void => {
                this.vm.load();
              } })
            }
            .width('100%')
            .height(220)
          } else if (this.vm.empty) {
            Column() {
              EmptyView({
                hint: '暂无正式模型评价记录',
                subHint: '待 B 角色交付正式评价（CNewSum test）后，数据将显示在此处'
              })
            }
            .width('100%')
            .height(220)
          } else {
            this.metricsCard(this.vm.metrics)
          }

          // 关于信息卡片
          Column({ space: 8 }) {
            Text('关于系统')
              .fontSize(15)
              .fontWeight(FontWeight.Medium)
              .fontColor('#1C1C1E')
              .width('100%')
            Text('基于自然语言处理的新闻文章自动摘要系统（HarmonyOS 客户端，阶段 4 完整实现）')
              .fontSize(13)
              .fontColor('#5A5F6A')
              .lineHeight(20)
              .width('100%')
            Text(`后端地址：${ApiConfig.baseUrl}`)
              .fontSize(12)
              .fontColor('#8A8F99')
              .width('100%')
            Text('新闻数据与摘要均通过 REST API 获取；客户端不直连 MySQL，也不调用 Python AI。')
              .fontSize(12)
              .fontColor('#8A8F99')
              .lineHeight(18)
              .width('100%')
          }
          .width('100%')
          .padding(14)
          .backgroundColor('#FFFFFF')
          .borderRadius(12)
          .alignItems(HorizontalAlign.Start)
        }
        .width('100%')
        .padding({ left: 12, right: 12, top: 4, bottom: 16 })
      }
      .layoutWeight(1)
      .width('100%')
      .scrollBar(BarState.Off)
      .align(Alignment.Top)
    }
    .width('100%')
    .height('100%')
    .backgroundColor('#F5F6FA')
  }

  /** 指标条目行。 */
  @Builder
  metricRow(label: string, value: string) {
    Row() {
      Text(label)
        .fontSize(13)
        .fontColor('#5A5F6A')
      Blank()
      Text(value)
        .fontSize(13)
        .fontColor('#1C1C1E')
        .fontWeight(FontWeight.Medium)
    }
    .width('100%')
  }

  /** 模型评价指标卡片。 */
  @Builder
  metricsCard(data: MetricsData | null) {
    if (data !== null) {
      Column({ space: 10 }) {
      Row() {
        Column({ space: 2 }) {
          Text(data.model_name)
            .fontSize(16)
            .fontWeight(FontWeight.Bold)
            .fontColor('#1C1C1E')
            .maxLines(1)
            .textOverflow({ overflow: TextOverflow.Ellipsis })
          Text(`版本 ${data.model_version}`)
            .fontSize(11)
            .fontColor('#B0B4BC')
        }
        .alignItems(HorizontalAlign.Start)
        .layoutWeight(1)
        Text('正式模型')
          .fontSize(10)
          .fontColor(Color.White)
          .padding({ left: 8, right: 8, top: 3, bottom: 3 })
          .borderRadius(10)
          .backgroundColor('#2B6BFF')
      }
      .width('100%')

      Divider().color('#EEF0F3')

      this.metricRow('评价数据集', `${data.dataset} / ${data.dataset_split}`)
      this.metricRow('评价样本数', `${data.sample_count}`)
      this.metricRow('ROUGE-1', `${data.rouge1.toFixed(4)}`)
      this.metricRow('ROUGE-2', `${data.rouge2.toFixed(4)}`)
      this.metricRow('ROUGE-L', `${data.rougeL.toFixed(4)}`)
      this.metricRow('平均生成耗时', `${data.avg_generation_time_ms} ms`)
      this.metricRow('P95 生成耗时', `${data.p95_generation_time_ms} ms`)
    }
    .width('100%')
    .padding(14)
    .backgroundColor('#FFFFFF')
    .borderRadius(12)
    .alignItems(HorizontalAlign.Start)
    }
  }
}

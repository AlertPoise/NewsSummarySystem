/**
 * 关于视图（E4-05 配套）。
 * 模型指标（E4-16）来自 GET /api/model/metrics，不硬编码任何数值：
 * 服务端存在正式评价记录（B 已交付）时自动展示指标卡片；
 * 无记录期间不展示该区块，避免“待交付”空态长期占位（B 交付后无需改码即可出现）。
 */

import { MetricsViewModel } from '../viewmodel/MetricsViewModel';
import { MetricsData } from '../model/News';
import { ApiConfig } from '../common/ApiConfig';
import { HttpClient } from '../common/HttpClient';

@Component
export struct AboutView {
  @State vm: MetricsViewModel = new MetricsViewModel();
  /** 服务连接测试状态：idle 未测 / testing 进行中 / ok 正常 / fail 失败。 */
  @State healthState: string = 'idle';
  /** 服务连接测试结果文案（成功含 status，失败含原因）。 */
  @State healthMessage: string = '';
  /** 健康检查客户端（仅调试用途，见 API.md GET /api/health 调用者说明）。 */
  private healthClient: HttpClient = new HttpClient();

  aboutToAppear(): void {
    this.vm.load();
  }

  build() {
    Column() {
      Row() {
        Text('关于')
          .fontSize(20)
          .fontWeight(FontWeight.Bold)
          .fontColor('#1C1C1E')
        Blank()
        if (this.vm.metrics !== null) {
          Text('刷新指标')
            .fontSize(14)
            .fontColor('#2B6BFF')
            .onClick(() => {
              this.vm.load();
            })
        }
      }
      .width('100%')
      .padding({ left: 12, right: 12, top: 10, bottom: 6 })

      Scroll() {
        Column({ space: 12 }) {
          // 模型指标卡：仅当服务端返回正式评价记录时渲染（无记录不占位）
          if (this.vm.metrics !== null) {
            this.metricsCard(this.vm.metrics)
          }

          // 关于系统卡片
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
            Row({ space: 10 }) {
              Text('服务连接')
                .fontSize(12)
                .fontColor('#8A8F99')
              if (this.healthState === 'testing') {
                LoadingProgress()
                  .width(14)
                  .height(14)
                  .color('#2B6BFF')
              } else {
                Text('测试连接')
                  .fontSize(12)
                  .fontColor('#2B6BFF')
                  .onClick(() => {
                    this.testConnection();
                  })
              }
              Text(this.healthMessage)
                .fontSize(12)
                .fontColor(this.healthState === 'ok' ? '#2BA471' : '#E5484D')
                .maxLines(1)
                .textOverflow({ overflow: TextOverflow.Ellipsis })
                .layoutWeight(1)
            }
            .width('100%')
            .alignItems(VerticalAlign.Center)
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

  /** 发起健康检查（GET /api/health），结果写入 healthState/healthMessage。 */
  private async testConnection(): Promise<void> {
    if (this.healthState === 'testing') {
      return;
    }
    this.healthState = 'testing';
    this.healthMessage = '';
    try {
      const status: string = await this.healthClient.getHealth();
      this.healthState = 'ok';
      this.healthMessage = `连接正常（status=${status}）`;
    } catch (err) {
      this.healthState = 'fail';
      this.healthMessage = `连接失败：${err.message}`;
    }
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

  /** 模型评价指标卡片（仅在服务端有正式评价记录时展示）。 */
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

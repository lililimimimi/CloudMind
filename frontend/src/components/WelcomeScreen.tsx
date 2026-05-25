// src/components/WelcomeScreen.tsx
import {
  BarChartOutlined,
  CustomerServiceOutlined,
  FileTextOutlined,
  GiftOutlined,
  RightOutlined,
} from "@ant-design/icons";

interface Props {
  onSend: (query: string) => void;
}

const cards = [
  {
    icon: <CustomerServiceOutlined />,
    title: "产品咨询与推荐",
    tone: "blue",
    items: [
      "云服务器ECS有哪些基本属性？",
      "Java服务 + MySQL，推荐具体实例型号",
    ],
  },
  {
    icon: <FileTextOutlined />,
    title: "账单与实例查询",
    tone: "violet",
    items: ["帮我查一下我最近的订单记录", "查询我名下所有运行中的实例"],
  },
  {
    icon: <BarChartOutlined />,
    title: "资源优化与降本",
    tone: "green",
    items: ["获取近7天资源监控并给降本建议", "服务器利用率低，怎么省钱？"],
  },
  {
    icon: <GiftOutlined />,
    title: "产品推广活动",
    tone: "orange",
    items: [
      "我想推广云服务器ECS，有海报吗？",
      "帮我生成一张C7计算型的推广海报",
    ],
  },
];

function BotHero() {
  return (
    <div className="bot-hero" aria-hidden="true">
      <div className="bot-orbit" />
      <div className="bot-headset left" />
      <div className="bot-headset right" />
      <div className="bot-head">
        <span />
        <span />
      </div>
      <div className="bot-glow" />
      <div className="bot-base">
        <div />
      </div>
    </div>
  );
}

function WelcomeScreen({ onSend }: Props) {
  return (
    <div className="welcome-screen">
      <section className="welcome-banner">
        <div className="welcome-copy">
          <h2>欢迎使用云平台智能客服</h2>
          <p>
            我是您的专属 AI 助手，您可以直接向我提问，
            <br />
            或尝试以下典型场景：
          </p>
        </div>
        <BotHero />
      </section>

      <section className="scenario-grid" aria-label="典型场景">
        {cards.map((card) => (
          <article className="scenario-card" key={card.title}>
            <div className="scenario-title">
              <div className={`scenario-icon ${card.tone}`}>{card.icon}</div>
              <h3>{card.title}</h3>
            </div>

            <div className="question-list">
              {card.items.map((item) => (
                <button
                  className="question-row"
                  key={item}
                  onClick={() => onSend(item)}
                  type="button"
                >
                  <span>{item}</span>
                  <RightOutlined />
                </button>
              ))}
            </div>
          </article>
        ))}
      </section>
    </div>
  );
}

export default WelcomeScreen;

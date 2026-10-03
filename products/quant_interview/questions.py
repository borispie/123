"""量化 / 数据岗面试概率题库（v1，30 道）。

每道题的字段：
  id        题号：P 条件概率 / E 期望 / M 随机过程 / G 连续分布 / S 统计推断
  topic     题型（卡片和 PDF 上显示）
  level     难度 1–3
  title     小红书标题（不超过 20 个字）
  hook      封面大字，每个元素一行
  fx        封面公式栏里的式子
  q_zh / q_en  题目（中 / 英）
  hint      提示
  answer    答案（一句话）
  value     答案的精确值（公式算的），用来和模拟对比
  steps     解法步骤
  say_en    面试时英文怎么说
  trap      常见错误
  followup  追问 + 答案
  snippet   模拟代码（numpy，seed = 0）。运行后必须有变量 result
  checks    [(项目, 公式值, 模拟表达式 或 None, 允许误差)]，第一行就是主答案
  finance   True 的题卡片上加「不构成投资建议」

题目都是经典概率题，文字、解析和代码是自己写的。
加题：照格式加一个 dict，再跑 python -m pytest tests/test_quant_bank.py，模拟和公式对不上会报错。
"""
from __future__ import annotations

import math
from textwrap import dedent

SQRT = math.sqrt

# 精确双侧 p 值：公平硬币抛 100 次，|正面数 − 50| ≥ 10
_P_EXACT_60 = 2 * sum(math.comb(100, k) for k in range(60, 101)) / 2 ** 100
# 凯利：0.6 ln(1+f) + 0.4 ln(1−f) = 0 的正根（二分法算的）
_KELLY_ZERO = 0.389391

TOPICS = {
    "P": "条件概率",
    "E": "期望",
    "M": "随机过程",
    "G": "连续分布",
    "S": "统计推断",
}


def _code(s: str) -> str:
    return dedent(s).strip("\n")


QUESTIONS: list[dict] = [
    # ---------------- P 条件概率 ----------------
    dict(
        id="P1", topic="条件概率 · 贝叶斯", level=1,
        title="检测阳性，真得病概率只有16%？",
        hook=["检测阳性", "真得病的概率", "只有 16%？"],
        fx="=P(有病 | 阳性)",
        q_zh="某种病的患病率是 1%。检测：真有病的人，95% 会测出阳性；没病的人，也有 5% 会被误判成阳性。"
             "随便找一个人去测，结果是阳性。他真的有病的概率是多少？",
        q_en="A disease affects 1% of people. The test is positive for 95% of sick people and for 5% of "
             "healthy people. A random person tests positive. What's the probability they're actually sick?",
        hint="想象 10000 个人，数一数测出阳性的人里，有几个是真病人。",
        answer="≈ 16.1%",
        value=0.95 * 0.01 / (0.95 * 0.01 + 0.05 * 0.99),
        steps=[
            "想象 10000 人：有病 100 人，没病 9900 人。",
            "有病的阳性：100 × 95% = 95 人；没病的阳性：9900 × 5% = 495 人。",
            "阳性一共 590 人，真病人 95 个 → 95 / 590 ≈ 16.1%。",
            "患病率太低，假阳性（495）比真阳性（95）多 5 倍多。",
        ],
        say_en="By Bayes' rule, P(sick | positive) = 0.95 × 0.01 / (0.95 × 0.01 + 0.05 × 0.99) ≈ 16%. "
               "The base rate is so low that false positives outnumber true positives about five to one.",
        trap="直接答 95%：把 P(阳性 | 有病) 当成了 P(有病 | 阳性)。",
        followup="他再测一次（两次结果独立），又是阳性，现在有病的概率是多少？→ 约 78.5%（把 16.1% 当成新的先验再算一次）。",
        snippet=_code("""
            rng = np.random.default_rng(0)
            n = 1_000_000
            sick = rng.random(n) < 0.01
            pos = np.where(sick, rng.random(n) < 0.95,
                           rng.random(n) < 0.05)
            result = sick[pos].mean()  # 阳性里真病人的比例
        """),
        checks=[("阳性里真有病的比例", 0.95 * 0.01 / (0.95 * 0.01 + 0.05 * 0.99), "result", 0.006)],
    ),
    dict(
        id="P2", topic="条件概率", level=1,
        title="至少一个男孩，两个都是男孩的概率？",
        hook=["两个孩子", "至少一个是男孩", "两个都是男孩的概率？"],
        fx="=P(两个男孩 | 至少一个男孩)",
        q_zh="一个家庭有两个孩子。已知至少有一个是男孩，两个都是男孩的概率是多少？（每个孩子是男孩的概率 1/2，互相独立）",
        q_en="A family has two children. Given that at least one is a boy, what's the probability that both are boys? "
             "(Each child is a boy with probability 1/2, independently.)",
        hint="把所有等可能的情况列出来，再划掉不符合条件的。",
        answer="1/3",
        value=1 / 3,
        steps=[
            "等可能的情况：男男、男女、女男、女女，各 1/4。",
            "「至少一个男孩」排除了女女，剩 3 种。",
            "两个都是男孩只有「男男」这 1 种 → 1/3。",
        ],
        say_en="Conditioning on at least one boy leaves three equally likely cases: BB, BG and GB. "
               "Only one of them is BB, so the answer is 1/3.",
        trap="答 1/2：把「至少一个是男孩」理解成了「老大是男孩」。",
        followup="如果条件换成「老大是男孩」呢？→ 1/2。条件不一样，剩下的样本空间就不一样。",
        snippet=_code("""
            rng = np.random.default_rng(0)
            boys = rng.random((1_000_000, 2)) < 0.5
            cond = boys.any(axis=1)  # 至少一个男孩
            result = boys.all(axis=1)[cond].mean()
        """),
        checks=[("两个都是男孩", 1 / 3, "result", 0.003)],
    ),
    dict(
        id="P3", topic="条件概率 · 三门问题", level=1,
        title="三门问题：换门赢车的概率是2/3",
        hook=["主持人开了一扇羊", "你换不换？"],
        fx="=P(换门赢)",
        q_zh="三扇门，一扇后面是车，两扇后面是羊。你先选了 1 号门。主持人知道车在哪，他从另外两扇里打开一扇羊。"
             "现在你可以换到剩下那扇门。换还是不换？换的话赢车的概率是多少？",
        q_en="There are three doors: a car behind one, goats behind the other two. You pick door 1. The host, who knows "
             "where the car is, opens another door showing a goat. Should you switch? What's your chance of winning if you do?",
        hint="你第一次就选中车的概率是多少？主持人开门会改变这个概率吗？",
        answer="换。换了赢的概率是 2/3",
        value=2 / 3,
        steps=[
            "第一次选中车的概率 1/3，选中羊的概率 2/3。",
            "如果第一次选的是羊，主持人只能打开另一只羊，剩下那扇一定是车。",
            "所以「换」能赢 ⇔ 第一次选到羊 → 概率 2/3。",
            "关键：主持人知道车在哪，而且一定开羊。他开门不是随机的。",
        ],
        say_en="Switch. My first pick is right with probability 1/3. If I picked a goat, which happens with probability 2/3, "
               "the host is forced to reveal the other goat, so switching wins. Switching wins with probability 2/3.",
        trap="答 1/2：忽略了主持人「知道答案、故意开羊」这个信息。",
        followup="如果主持人是随便开一扇，刚好开出了羊呢？→ 这时换不换都是 1/2。",
        snippet=_code("""
            rng = np.random.default_rng(0)
            n = 1_000_000
            car = rng.integers(0, 3, n)  # 你先选 0 号门
            # 车在 0 号时随便开
            goat = rng.integers(1, 3, n)
            opened = np.where(car == 0, goat, 3 - car)
            switch = 3 - opened  # 换到剩下那扇
            result = (switch == car).mean()
        """),
        checks=[("换门赢的概率", 2 / 3, "result", 0.003)],
    ),
    dict(
        id="P4", topic="条件概率 · 贝叶斯", level=2,
        title="连抛5次正面，硬币有问题的概率？",
        hook=["连抛 5 次", "全是正面", "这枚硬币有问题吗？"],
        fx="=P(双正面 | 5次全正)",
        q_zh="袋子里有 10 枚硬币，其中 1 枚两面都是正面，另外 9 枚是普通硬币。你随便摸一枚，连抛 5 次，全是正面。"
             "这枚是双正面硬币的概率是多少？",
        q_en="A bag has 10 coins: one is double-headed and the other 9 are fair. You pick one at random and flip it 5 times. "
             "All five are heads. What's the probability you picked the double-headed coin?",
        hint="贝叶斯：先验是 1/10。「5 次全正」在两种硬币下的概率分别是多少？",
        answer="32/41 ≈ 78.0%",
        value=32 / 41,
        steps=[
            "先验：双正面 1/10，普通 9/10。",
            "似然：双正面抛 5 次全正的概率 = 1；普通硬币 = (1/2)⁵ = 1/32。",
            "后验 = (1/10 × 1) / (1/10 × 1 + 9/10 × 1/32) = 32/41 ≈ 78.0%。",
        ],
        say_en="The prior for the double-headed coin is 1/10. Five heads has likelihood 1 for it and 1/32 for a fair coin. "
               "The posterior is (1/10) / (1/10 + 9/10 × 1/32) = 32/41, about 78%.",
        trap="看到 5 次全正就觉得「肯定是双正面」：忘了先验只有 10%。",
        followup="第 6 次再抛出正面的概率？→ 32/41 × 1 + 9/41 × 1/2 = 73/82 ≈ 89.0%。",
        snippet=_code("""
            rng = np.random.default_rng(0)
            n = 1_000_000
            fake = rng.random(n) < 0.1  # 摸到双正面
            heads = np.where(fake, 5, rng.binomial(5, 0.5, n))
            result = fake[heads == 5].mean()
        """),
        checks=[("是双正面硬币的概率", 32 / 41, "result", 0.006)],
    ),
    dict(
        id="P5", topic="组合计数 · 生日问题", level=1,
        title="多少人里，有人同一天生日的概率过半？",
        hook=["只要 23 个人", "就有一半概率", "有人同一天生日"],
        fx="=MIN(n): P(撞生日) > 50%",
        q_zh="一个房间里至少要有多少人，「至少两个人同一天生日」的概率才会超过 50%？（一年按 365 天，生日均匀分布，不考虑闰年）",
        q_en="How many people do you need in a room for the probability that at least two share a birthday to exceed 50%? "
             "(Assume 365 equally likely days and ignore leap years.)",
        hint="算反面：所有人生日都不一样的概率。",
        answer="23 人（这时概率 ≈ 50.7%）",
        value=23,
        steps=[
            "n 个人生日全不同的概率 = 365/365 × 364/365 × … × (365−n+1)/365。",
            "至少两人同一天 = 1 − 上面这个数。",
            "n = 22 时约 47.6%，n = 23 时约 50.7%。",
            "直觉：23 个人能组成 C(23,2) = 253 对，每一对都可能撞。",
        ],
        say_en="Compute the complement: all birthdays distinct has probability 365 × 364 × … × (365 − n + 1) / 365ⁿ. "
               "It drops below one half at n = 23, where the chance of a shared birthday is about 50.7%. "
               "The intuition is that 23 people form 253 pairs.",
        trap="答 183（365 的一半）：想的是「有人和我同一天」，不是「任意两个人同一天」。",
        followup="至少多少人，「有人和你同一天生日」的概率才超过 50%？→ 253 人（不算你自己）。",
        snippet=_code("""
            rng = np.random.default_rng(0)
            # k 个人撞生日的概率
            def p_shared(k, n=200_000):
                b = np.sort(rng.integers(0, 365, (n, k)))
                return (np.diff(b) == 0).any(axis=1).mean()
            result = next(k for k in range(15, 40)
                          if p_shared(k) > 0.5)
            p23 = p_shared(23)
        """),
        checks=[
            ("最少人数", 23, "result", 0),
            ("23 人时撞生日的概率", 0.507297, "p23", 0.006),
        ],
    ),
    dict(
        id="P6", topic="条件概率 · 对称性", level=2,
        title="丢了登机牌乱坐，最后一人坐对的概率",
        hook=["第 1 个人乱坐", "最后 1 个人", "坐到自己座位的概率？"],
        fx="=P(最后一人坐对)",
        q_zh="100 个人排队登机，飞机正好 100 个座位，每人都有座位号。第 1 个人丢了登机牌，随便坐了一个座位。"
             "之后每个人：自己的座位空着就坐自己的，被占了就从空座里随便挑一个。最后一个人坐到自己座位的概率是多少？",
        q_en="100 passengers board a 100-seat plane, each with an assigned seat. The first passenger lost their boarding pass "
             "and sits in a random seat. Everyone after takes their own seat if it's free, otherwise a random free seat. "
             "What's the probability the last passenger gets their own seat?",
        hint="最后一个人上飞机时，剩下的那个座位只可能是哪几个？",
        answer="1/2",
        value=0.5,
        steps=[
            "只要有人坐了 1 号座（第 1 个人的座位），后面的人都能坐自己的座，最后一个人成功。",
            "只要有人坐了 100 号座（最后一个人的座位），最后一个人就失败。",
            "每次有人「随便挑」时，挑到 1 号和挑到 100 号的机会一样。",
            "所以最后剩下的座位是 1 号还是 100 号，各占 1/2。",
        ],
        say_en="Whenever someone picks at random, seat 1 and seat 100 are symmetric. The process succeeds as soon as seat 1 "
               "is taken and fails as soon as seat 100 is taken, so the last seat is equally likely to be either: 1/2.",
        trap="硬算 100 层条件概率，算不出来。这题要找对称性。",
        followup="倒数第二个人坐到自己座位的概率？→ 2/3。",
        snippet=_code("""
            rng = np.random.default_rng(0)
            n, N = 100, 200_000
            # 被挤走的人，先是 1 号
            s = np.ones(N, dtype=int)
            end = np.zeros(N, dtype=int)
            while (end == 0).any():
                i = np.flatnonzero(end == 0)
                # 空座只有 1 号和 s+1..n 号
                k = rng.integers(0, n - s[i] + 1)
                seat = np.where(k == 0, 1, s[i] + k)
                s[i] = seat
                end[i] = (seat == 1) + 2 * (seat == n)
            result = (end == 1).mean()  # 最后一人坐对
        """),
        checks=[("最后一人坐到自己座位", 0.5, "result", 0.006)],
    ),
    # ---------------- E 期望 ----------------
    dict(
        id="E1", topic="期望 · 集卡问题", level=1,
        title="掷骰子集齐6个点数，平均要几次？",
        hook=["掷骰子", "集齐 1 到 6", "平均要掷几次？"],
        fx="=E[集齐 6 面的次数]",
        q_zh="不停地掷一个公平的骰子，平均要掷多少次，1 到 6 每个点数才都至少出现过一次？",
        q_en="You roll a fair die repeatedly. What's the expected number of rolls until you've seen all six faces at least once?",
        hint="拆成 6 段：已经集到 k 种点数之后，等下一个「新点数」平均要多久？",
        answer="14.7 次（= 6 × (1 + 1/2 + … + 1/6)）",
        value=6 * sum(1 / k for k in range(1, 7)),
        steps=[
            "已经集到 k 种点数时，下一次掷出新点数的概率是 (6−k)/6。",
            "等它出现平均要 6/(6−k) 次（几何分布）。",
            "加起来：6/6 + 6/5 + 6/4 + 6/3 + 6/2 + 6/1 = 6 × 2.45 = 14.7。",
            "最后一个点数最难等，平均就要 6 次。",
        ],
        say_en="Split it into stages. After collecting k faces, each roll gives a new face with probability (6 − k)/6, "
               "so that stage takes 6/(6 − k) rolls on average. Summing over k = 0 to 5 gives 6 × (1 + 1/2 + … + 1/6) = 14.7.",
        trap="答 6 次或 12 次：忘了越往后，新点数越难出。",
        followup="集齐 n 种卡片大概要多少次？→ n × (1 + 1/2 + … + 1/n) ≈ n·ln n + 0.577n，n = 100 时约 519 次。",
        snippet=_code("""
            rng = np.random.default_rng(0)
            N = 200_000
            seen = np.zeros((N, 6), dtype=bool)
            rolls = np.zeros(N, dtype=int)
            left = np.arange(N)  # 还没集齐的
            while left.size:
                face = rng.integers(0, 6, left.size)
                seen[left, face] = True
                rolls[left] += 1
                left = left[~seen[left].all(axis=1)]
            result = rolls.mean()
        """),
        checks=[("平均掷几次", 6 * sum(1 / k for k in range(1, 7)), "result", 0.08)],
    ),
    dict(
        id="E2", topic="期望 · 最大值", level=1,
        title="两个骰子取较大值，期望是多少？",
        hook=["两个骰子", "取大的那个", "期望是多少？"],
        fx="=E[MAX(骰子1, 骰子2)]",
        q_zh="同时掷两个公平骰子，取两个点数里较大的那个。它的期望是多少？",
        q_en="Roll two fair dice and take the larger of the two numbers. What's its expected value?",
        hint="先算「较大值 ≤ k」的概率。",
        answer="161/36 ≈ 4.47",
        value=161 / 36,
        steps=[
            "较大值 ≤ k ⇔ 两个都 ≤ k，概率 (k/6)²。",
            "P(较大值 = k) = (k² − (k−1)²)/36 = (2k−1)/36。",
            "E = Σ k(2k−1)/36 = (1 + 6 + 15 + 28 + 45 + 66)/36 = 161/36 ≈ 4.47。",
        ],
        say_en="P(max ≤ k) = (k/6)², so P(max = k) = (2k − 1)/36. "
               "The expectation is Σ k(2k − 1)/36 = 161/36, about 4.47.",
        trap="答 3.5（那是一个骰子的期望）或者凭感觉说 5。",
        followup="较小值的期望？→ 7 − 161/36 = 91/36 ≈ 2.53（较大 + 较小 = 两个点数之和，期望是 7）。",
        snippet=_code("""
            rng = np.random.default_rng(0)
            d = rng.integers(1, 7, (1_000_000, 2))
            result = d.max(axis=1).mean()
        """),
        checks=[("较大值的期望", 161 / 36, "result", 0.01)],
    ),
    dict(
        id="E3", topic="期望 · 线性性", level=1,
        title="10个人随机拿帽子，平均几人拿对？",
        hook=["10 个人", "随机拿帽子", "平均几个人拿对？"],
        fx="=E[拿对帽子的人数]",
        q_zh="10 个人把帽子放在一起，打乱后每人随机拿一顶。平均有几个人拿到自己的帽子？",
        q_en="Ten people put their hats in a pile and each takes one at random. On average, how many get their own hat back?",
        hint="不用算分布。给每个人一个 0/1 变量，用期望的线性性。",
        answer="1 个（不管多少人，都是 1）",
        value=1.0,
        steps=[
            "设 Xi = 1 表示第 i 个人拿到自己的帽子，否则 0。",
            "每个人拿到自己帽子的概率是 1/10，所以 E[Xi] = 1/10。",
            "期望的线性性：E[X1 + … + X10] = 10 × 1/10 = 1。",
            "线性性不需要独立。这些 Xi 明明不独立，照样能直接加。",
        ],
        say_en="Use indicator variables. Each person gets their own hat with probability 1/n, and by linearity of expectation, "
               "which doesn't need independence, the expected number of matches is n × 1/n = 1 for any n.",
        trap="去算「恰好 k 个人拿对」的分布再求期望：能做，但面试官想看你用线性性一行解决。",
        followup="一个人都没拿对的概率？→ n 很大时趋近 1/e ≈ 36.8%（10 个人时约 36.79%）。",
        snippet=_code("""
            rng = np.random.default_rng(0)
            N, n = 200_000, 10
            # 随机排列
            hats = rng.random((N, n)).argsort(axis=1)
            match = (hats == np.arange(n)).sum(axis=1)
            result = match.mean()
            none = (match == 0).mean()  # 追问：没人拿对
        """),
        checks=[
            ("平均拿对人数", 1.0, "result", 0.012),
            ("追问：没人拿对的概率", 0.367879, "none", 0.006),
        ],
    ),
    dict(
        id="E4", topic="期望 · 对称性", level=2,
        title="洗好的牌里，第一张A前平均几张？",
        hook=["一副牌洗匀", "第一张 A 前面", "平均有几张牌？"],
        fx="=E[第一张 A 前的牌数]",
        q_zh="一副 52 张扑克牌洗匀后一张张翻开。第一张 A 出现之前，平均会翻出几张别的牌？",
        q_en="Shuffle a standard 52-card deck and turn the cards over one by one. On average, how many non-ace cards "
             "appear before the first ace?",
        hint="4 张 A 把另外 48 张牌分成了 5 段。",
        answer="48/5 = 9.6 张",
        value=9.6,
        steps=[
            "4 张 A 把牌堆分成 5 段：第一张 A 前、A 和 A 之间（3 段）、最后一张 A 后。",
            "每张非 A 牌落在这 5 段里的机会一样，都是 1/5（对称性）。",
            "第一段的期望张数 = 48 × 1/5 = 9.6。",
        ],
        say_en="The four aces split the other 48 cards into five gaps. By symmetry each non-ace is equally likely to land "
               "in any gap, so the expected number before the first ace is 48/5 = 9.6.",
        trap="答 52/4 = 13 或 48/4 = 12：空隙是 5 个，不是 4 个。",
        followup="第一张 A 平均出现在第几张？→ 9.6 + 1 = 10.6 张。",
        snippet=_code("""
            rng = np.random.default_rng(0)
            N = 100_000
            # 0–3 是 A
            deck = rng.random((N, 52)).argsort(axis=1)
            # 第一张 A 的下标
            first_ace = (deck < 4).argmax(axis=1)
            result = first_ace.mean()  # = 它前面有几张牌
        """),
        checks=[("第一张 A 前的平均张数", 9.6, "result", 0.15)],
    ),
    dict(
        id="E5", topic="期望 · 线性性", level=2,
        title="抛10次硬币，平均会出现几段连续？",
        hook=["抛 10 次硬币", "平均有几段", "连续相同？"],
        fx="=E[段数]",
        q_zh="抛一枚公平硬币 10 次，连续相同的结果算一段（比如「正正反正正正」是 3 段）。平均有几段？",
        q_en="Flip a fair coin 10 times. A run is a maximal block of identical outcomes (for example, HHTHHH has 3 runs). "
             "What's the expected number of runs?",
        hint="段数 = 1 + 「相邻两次结果不一样」的次数。",
        answer="5.5 段",
        value=5.5,
        steps=[
            "段数 = 1 + 相邻两次不一样的位置个数。",
            "10 次有 9 对相邻，每一对不一样的概率是 1/2。",
            "期望 = 1 + 9 × 1/2 = 5.5。",
        ],
        say_en="The number of runs equals one plus the number of places where consecutive flips differ. "
               "There are 9 adjacent pairs, each different with probability 1/2, so the expectation is 1 + 9/2 = 5.5.",
        trap="想去枚举 2¹⁰ = 1024 种情况：用指示变量一行就够了。",
        followup="如果硬币正面的概率是 p 呢？→ 1 + 9 × 2p(1 − p)。",
        snippet=_code("""
            rng = np.random.default_rng(0)
            flips = rng.integers(0, 2, (1_000_000, 10))
            changes = (np.diff(flips) != 0).sum(axis=1)
            result = (1 + changes).mean()
        """),
        checks=[("平均段数", 5.5, "result", 0.01)],
    ),
    dict(
        id="E6", topic="期望 · 破纪录", level=2,
        title="1到10随机排一排，平均破几次纪录？",
        hook=["1 到 10 随机排", "「破纪录」", "平均只有几次？"],
        fx="=E[破纪录次数]",
        q_zh="把 1 到 10 随机打乱排成一排，从左往右看。一个数如果比它左边所有的数都大，就算一次「破纪录」（第一个数一定算）。"
             "平均有几次破纪录？",
        q_en="Shuffle the numbers 1 to 10 and read them left to right. A number is a record if it's larger than everything "
             "before it (the first one always counts). What's the expected number of records?",
        hint="第 k 个位置破纪录的概率是多少？",
        answer="1 + 1/2 + … + 1/10 ≈ 2.93 次",
        value=sum(1 / k for k in range(1, 11)),
        steps=[
            "第 k 个数破纪录 ⇔ 它是前 k 个数里最大的。",
            "前 k 个数里每个数当最大的机会一样，所以概率是 1/k。",
            "期望 = 1 + 1/2 + 1/3 + … + 1/10 ≈ 2.93。",
        ],
        say_en="Position k is a record exactly when it's the largest of the first k numbers, which has probability 1/k "
               "by symmetry. Summing gives the harmonic number H₁₀ ≈ 2.93.",
        trap="觉得要 5 次左右：越往后越难破纪录，次数只按 ln n 的速度涨。",
        followup="1000 个数呢？→ 约 7.49 次，连 8 次都不到。",
        snippet=_code("""
            rng = np.random.default_rng(0)
            # 随机排列
            x = rng.random((200_000, 10)).argsort(axis=1)
            records = x == np.maximum.accumulate(x, axis=1)
            result = records.sum(axis=1).mean()
        """),
        checks=[("平均破纪录次数", sum(1 / k for k in range(1, 11)), "result", 0.015)],
    ),
    # ---------------- M 随机过程 ----------------
    dict(
        id="M1", topic="随机过程 · 等待时间", level=2,
        title="等「正正」6次，等「正反」只要4次？",
        hook=["等「正正」要 6 次", "等「正反」只要 4 次", "为什么？"],
        fx="=E[等到「正正」的次数]",
        q_zh="不停地抛公平硬币。平均要抛多少次，才第一次出现连续两个正面（正正）？如果等的是「正反」呢？",
        q_en="Flip a fair coin repeatedly. What's the expected number of flips until you first see two heads in a row (HH)? "
             "What about HT?",
        hint="设两个状态：「上一次是正面」和「从头开始」，列期望方程。",
        answer="正正：6 次；正反：4 次",
        value=6.0,
        steps=[
            "等「正正」：E0 = 从头开始的期望次数，E1 = 刚抛出一个正面时的期望次数。",
            "E0 = 1 + ½E1 + ½E0，E1 = 1 + ½ × 0 + ½E0，解出 E0 = 6。",
            "等「正反」：先等第一个正面（平均 2 次），再等第一个反面（平均 2 次），一共 4 次。",
            "区别：「正正」失败时（抛出反面）要从头再来；「正反」失败时（又是正面）还停在「有一个正」的状态。",
        ],
        say_en="Set up states. For HH, E0 = 1 + ½E1 + ½E0 and E1 = 1 + ½E0, which gives E0 = 6. For HT it's 4: "
               "wait for the first head (2 flips on average), then for the first tail (another 2). "
               "HH is slower because a failure sends you back to the start.",
        trap="觉得两个一样都是 4 次：每种组合出现的概率确实都是 1/4，但等待时间不一样。",
        followup="等「正正正」呢？→ 14 次（规律：连续 k 个正面要 2^(k+1) − 2 次）。",
        snippet=_code("""
            rng = np.random.default_rng(0)
            f = rng.integers(0, 2, (200_000, 100), np.int8)
            # 1 = 正面
            hh = (f[:, :-1] == 1) & (f[:, 1:] == 1)
            ht = (f[:, :-1] == 1) & (f[:, 1:] == 0)
            # 第几次抛完
            result = hh.argmax(axis=1).mean() + 2
            wait_ht = ht.argmax(axis=1).mean() + 2
        """),
        checks=[
            ("等「正正」的平均次数", 6.0, "result", 0.08),
            ("等「正反」的平均次数", 4.0, "wait_ht", 0.04),
        ],
    ),
    dict(
        id="M2", topic="随机过程 · Penney 游戏", level=3,
        title="押「正正反」赢「正反正」的概率？",
        hook=["押「正正反」", "对「正反正」", "赢面是 2/3"],
        fx="=P(「正正反」先出现)",
        q_zh="两个人看同一串抛硬币的结果。A 押「正正反」，B 押「正反正」，谁押的组合先出现谁赢。A 赢的概率是多少？",
        q_en="Two players watch the same sequence of fair coin flips. A bets on HHT and B bets on HTH. "
             "Whoever's pattern appears first wins. What's the probability that A wins?",
        hint="一旦出现「正正」，B 还有机会吗？",
        answer="2/3",
        value=2 / 3,
        steps=[
            "两个组合都以「正」开头。等到第一个正面后，只需要看三种状态：正、正正、正反。",
            "一旦出现「正正」，A 必赢：再来正面还是「正正」，来反面就是「正正反」。",
            "设 p = 处在「正」时 A 赢的概率。下一次正面 → 「正正」（A 赢）；反面 → 「正反」。",
            "处在「正反」时：下一次正面 → B 赢；反面 → 回到起点，A 赢的概率还是 p。",
            "p = ½ × 1 + ½ × (½ × 0 + ½ × p)，解出 p = 2/3。",
        ],
        say_en="Once HH appears, A must win: more heads keep you at HH and the first tail completes HHT. "
               "From state H, A wins with probability p = ½ · 1 + ½ · (½ · 0 + ½ · p), so p = 2/3.",
        trap="觉得都是 3 位、所以各 1/2。也有人拿平均等待时间来比（正正反 8 次、正反正 10 次），但「谁先出现」不能直接这么推。",
        followup="A 改押「反正正」，B 押「正正反」呢？→ A 赢的概率 3/4。",
        snippet=_code("""
            rng = np.random.default_rng(0)
            f = rng.integers(0, 2, (200_000, 100), np.int8)
            def first(p):  # 组合 p 第一次出现的位置
                hit = np.ones(f[:, 2:].shape, dtype=bool)
                for j, c in enumerate(p):
                    hit &= f[:, j:98 + j] == c
                return np.where(hit.any(1), hit.argmax(1), 999)
            a, b = first([1, 1, 0]), first([1, 0, 1])
            result = (a < b).mean()  # 正正反 先出现
        """),
        checks=[("「正正反」先出现的概率", 2 / 3, "result", 0.006)],
    ),
    dict(
        id="M3", topic="随机过程 · 随机游走", level=2,
        title="3块钱抛硬币，先到10块的概率？",
        hook=["3 块钱抛硬币", "先到 10 块的概率", "只有 30%"],
        fx="=P(先到 10 块)",
        q_zh="你有 3 块钱，玩抛硬币游戏：正面赢 1 块，反面输 1 块。钱变成 10 块或者 0 块就停。最后到 10 块的概率是多少？平均要玩多少局？",
        q_en="You start with $3. Each round, a fair coin flip wins or loses $1. You stop at $10 or $0. "
             "What's the probability you reach $10? What's the expected number of rounds?",
        hint="公平游戏，钱的期望一直不变。停下来时的期望也应该是 3。",
        answer="到 10 块的概率 3/10；平均 21 局",
        value=0.3,
        steps=[
            "公平游戏里，钱的期望一直是 3（鞅 + 停时定理）。",
            "停下时只有 10 和 0 两种结果：10p + 0 × (1 − p) = 3 → p = 3/10。",
            "平均局数：从 k 出发、上限 N 时是 k(N − k) = 3 × 7 = 21 局。",
        ],
        say_en="My wealth is a martingale, so by optional stopping its expected value at the end is still 3. "
               "That gives 10p = 3, so p = 0.3. The expected duration of this fair random walk is k(N − k) = 3 × 7 = 21 rounds.",
        trap="凭「3 离 0 近」去猜一个数：用期望不变直接算，不用猜。",
        followup="如果每局赢的概率是 0.6 呢？→ 到 10 块的概率 = (1 − (2/3)³)/(1 − (2/3)¹⁰) ≈ 71.6%。",
        snippet=_code("""
            rng = np.random.default_rng(0)
            N = 200_000
            x = np.full(N, 3)
            rounds = np.zeros(N, dtype=int)
            alive = np.ones(N, dtype=bool)
            while alive.any():
                x[alive] += rng.choice([-1, 1], alive.sum())
                rounds[alive] += 1
                alive &= (x > 0) & (x < 10)
            result = (x == 10).mean()
        """),
        checks=[
            ("先到 10 块的概率", 0.3, "result", 0.006),
            ("平均局数", 21, "rounds.mean()", 0.3),
        ],
    ),
    dict(
        id="M4", topic="随机过程 · 最优停止", level=1,
        title="掷骰子能重掷一次，这游戏值多少钱？",
        hook=["掷骰子", "可以重掷一次", "这个游戏值多少钱？"],
        fx="=E[可以重掷时的收益]",
        q_zh="掷一个骰子，点数是几就给你几块钱。掷完你可以拿钱走人，也可以重掷一次（重掷后必须接受新的点数）。"
             "最优策略是什么？这个游戏值多少钱？",
        q_en="Roll a die and get paid its face value in dollars. After the first roll you may keep it or roll once more, "
             "and then you must keep the second roll. What's the optimal strategy and the game's fair value?",
        hint="重掷的期望是 3.5。第一次掷出几点才值得留下？",
        answer="掷出 1、2、3 就重掷，4、5、6 就留下；游戏值 4.25 元",
        value=4.25,
        steps=[
            "重掷一次的期望是 3.5。",
            "第一次的点数比 3.5 大就留下（4、5、6），否则重掷（1、2、3）。",
            "期望 = ½ × (4 + 5 + 6)/3 + ½ × 3.5 = 2.5 + 1.75 = 4.25。",
            "这个「可以选择」的权利本身值 4.25 − 3.5 = 0.75 元，就是期权的思路。",
        ],
        say_en="Work backwards. A reroll is worth 3.5, so keep 4, 5 or 6 and reroll 1, 2 or 3. "
               "The value is ½ × 5 + ½ × 3.5 = 4.25. The option to reroll is worth 0.75.",
        trap="答 3.5：没把「可以选择重掷」这个权利算进去。",
        followup="如果最多可以掷 3 次呢？→ 14/3 ≈ 4.67（第一次掷出 5、6 才留下，因为后面两次的价值是 4.25）。",
        snippet=_code("""
            rng = np.random.default_rng(0)
            r1, r2, r3 = rng.integers(1, 7, (3, 1_000_000))
            two = np.where(r1 >= 4, r1, r2)  # 最多掷 2 次
            three = np.where(r1 >= 5, r1,  # 最多掷 3 次
                             np.where(r2 >= 4, r2, r3))
            result = two.mean()
        """),
        checks=[
            ("最多掷 2 次的价值", 4.25, "result", 0.01),
            ("追问：最多掷 3 次", 14 / 3, "three.mean()", 0.01),
        ],
    ),
    dict(
        id="M5", topic="随机过程 · 递推", level=2,
        title="正面+1反面+2，恰好到10分的概率？",
        hook=["正面 +1 分", "反面 +2 分", "恰好到 10 分的概率？"],
        fx="=P(恰好到 10 分)",
        q_zh="抛公平硬币：正面得 1 分，反面得 2 分，分数一直累加。分数「恰好」等于 10 分的概率是多少？（也就是没有从 9 分直接跳到 11 分）",
        q_en="Flip a fair coin repeatedly: heads scores 1 point and tails scores 2. "
             "What's the probability that your running total ever equals exactly 10?",
        hint="唯一会错过 10 分的情况是什么？",
        answer="683/1024 ≈ 0.667（目标越大越接近 2/3）",
        value=683 / 1024,
        steps=[
            "唯一错过 n 的方式：先到了 n − 1，然后抛出反面（+2）。",
            "所以 p(n) = 1 − ½ × p(n − 1)，p(0) = 1。",
            "解出 p(n) = 2/3 + (1/3) × (−½)ⁿ。",
            "n = 10 时 = 683/1024 ≈ 0.667。",
        ],
        say_en="The only way to miss n is to be at n − 1 and then score 2. So p(n) = 1 − ½ p(n − 1) with p(0) = 1. "
               "The solution is p(n) = 2/3 + (1/3)(−½)ⁿ, which is 683/1024 ≈ 0.667 for n = 10.",
        trap="答 1/2：以为每个分数被踩到的机会是一半。",
        followup="为什么极限是 2/3？→ 平均每步走 1.5 分，长期看每 1.5 分踩中一个整数，1/1.5 = 2/3。",
        snippet=_code("""
            rng = np.random.default_rng(0)
            # 1 或 2 分
            steps = rng.integers(1, 3, (1_000_000, 10))
            total = steps.cumsum(axis=1)
            result = (total == 10).any(axis=1).mean()
        """),
        checks=[("恰好到 10 分的概率", 683 / 1024, "result", 0.003)],
    ),
    dict(
        id="M6", topic="随机过程 · 凯利公式", level=2, finance=True,
        title="胜率60%的游戏，每次该投入多少？",
        hook=["胜率 60%", "每次该投入多少？", "答案是 20%"],
        fx="=ARGMAX(长期增长率)",
        q_zh="有一个可以一直玩的游戏：每次投入本金的一部分，60% 的概率赚到和投入一样多，40% 的概率把投入的亏掉。"
             "每次投入本金的多少比例，本金长期涨得最快？",
        q_en="A repeatable bet wins with probability 60% at even odds: you gain what you stake or lose it. "
             "What fraction of your bankroll should you stake each time to maximize long-run growth?",
        hint="最大化每局的期望对数收益：g(f) = 0.6 ln(1 + f) + 0.4 ln(1 − f)。",
        answer="20%（凯利公式：f = p − q = 0.6 − 0.4）",
        value=0.2,
        steps=[
            "每次投入比例 f，长期增长率 g(f) = 0.6 ln(1 + f) + 0.4 ln(1 − f)。",
            "求导：0.6/(1 + f) − 0.4/(1 − f) = 0 → f = 0.2。",
            "投太多反而会亏：f 超过约 39% 时，g(f) 就变成负的了。",
            "f = 20% 时，每局的期望对数增长约 2.0%。",
        ],
        say_en="Maximize the expected log growth g(f) = p ln(1 + f) + q ln(1 − f). Setting the derivative to zero gives "
               "f* = p − q = 20%. Betting much more lowers long-run growth, and beyond about 39% growth turns negative.",
        trap="答 100%（期望为正就全押）：单局期望最大不等于长期涨得最快，全押输一次就归零。",
        followup="如果赢了能赚到投入的 2 倍、胜率 40% 呢？→ f = (2 × 0.4 − 0.6)/2 = 10%。",
        snippet=_code("""
            rng = np.random.default_rng(0)
            # 模拟 100 万局
            p = (rng.random(1_000_000) < 0.6).mean()
            f = np.linspace(0, 0.99, 100)  # 试 0%–99%
            g = p * np.log(1 + f) + (1 - p) * np.log(1 - f)
            result = f[g.argmax()]  # 涨得最快的比例
            # 开始变负的比例
            zero = f[(g < 0) & (f > 0)].min()
        """),
        checks=[
            ("长期涨得最快的比例", 0.2, "result", 0.011),
            ("该比例下每局对数增长", 0.6 * math.log(1.2) + 0.4 * math.log(0.8), "g.max()", 0.002),
            ("增长开始变负的比例", _KELLY_ZERO, "zero", 0.011),
        ],
    ),
    # ---------------- G 连续分布 ----------------
    dict(
        id="G1", topic="连续分布 · 均匀分布", level=3,
        title="随机数加到超过1，平均要几个？",
        hook=["随机数加到超过 1", "平均要几个？", "答案是 e"],
        fx="=E[和超过 1 要几个数]",
        q_zh="不断从 0 到 1 之间均匀地随机取数，累加起来，直到总和超过 1 为止。平均要取几个数？",
        q_en="Keep drawing independent Uniform(0, 1) numbers and adding them up until the sum exceeds 1. "
             "What's the expected number of draws?",
        hint="前 n 个数的和还 ≤ 1 的概率是多少？（想想单纯形的体积）",
        answer="e ≈ 2.718",
        value=math.e,
        steps=[
            "设 N 是取数的个数。N > n ⇔ 前 n 个数的和 ≤ 1。",
            "n 个均匀数的和 ≤ 1 的概率 = 1/n!（n 维单纯形的体积）。",
            "E[N] = Σ P(N > n)（n 从 0 开始）= 1 + 1 + 1/2! + 1/3! + … = e。",
        ],
        say_en="N exceeds n exactly when the first n uniforms sum to at most 1, which has probability 1/n!, "
               "the volume of a simplex. So E[N] = Σ P(N > n) = Σ 1/n! = e.",
        trap="答 2：两个数的和平均是 1，但要「超过 1」，需要的个数会多一点。",
        followup="停下来时，总和平均是多少？→ e/2 ≈ 1.359（Wald 等式：E[N] × 1/2）。",
        snippet=_code("""
            rng = np.random.default_rng(0)
            u = rng.random((300_000, 15))
            s = u.cumsum(axis=1)
            n = (s > 1).argmax(axis=1) + 1  # 第几个数超过 1
            result = n.mean()
            # 追问
            final = s[np.arange(len(n)), n - 1].mean()
        """),
        checks=[
            ("平均要取几个数", math.e, "result", 0.008),
            ("追问：停下时总和的平均", math.e / 2, "final", 0.004),
        ],
    ),
    dict(
        id="G2", topic="连续分布 · 顺序统计量", level=1,
        title="随机取3个0到1的数，最大的平均多少？",
        hook=["随机取 3 个数", "最大的那个", "平均是多少？"],
        fx="=E[MAX(U1, U2, U3)]",
        q_zh="从 0 到 1 之间均匀随机取 3 个数，最大的那个平均是多少？",
        q_en="Draw three independent Uniform(0, 1) numbers. What's the expected value of the largest?",
        hint="P(最大值 ≤ x) = x³。",
        answer="3/4",
        value=0.75,
        steps=[
            "最大值 ≤ x ⇔ 三个数都 ≤ x，概率是 x³。",
            "期望 = ∫₀¹ P(最大值 > x) dx = ∫₀¹ (1 − x³) dx = 1 − 1/4 = 3/4。",
            "一般地：n 个数的最大值期望 n/(n+1)，最小值期望 1/(n+1)。",
        ],
        say_en="The CDF of the max is x³, so E[max] = ∫(1 − x³) dx = 3/4. In general the max of n uniforms has mean "
               "n/(n + 1): the n points split [0, 1] into n + 1 gaps with equal expected length.",
        trap="答 2/3，或者闷头积分算很久。记住「n 个点把区间平均分成 n + 1 段」。",
        followup="中间那个数平均是多少？→ 1/2。n 个数里第 k 小的平均是 k/(n + 1)。",
        snippet=_code("""
            rng = np.random.default_rng(0)
            u = rng.random((1_000_000, 3))
            result = u.max(axis=1).mean()
        """),
        checks=[("最大值的期望", 0.75, "result", 0.0015)],
    ),
    dict(
        id="G3", topic="连续分布 · 几何概率", level=2,
        title="圆上随机3点，三角形包住圆心的概率？",
        hook=["圆上随机 3 个点", "三角形包住圆心", "概率只有 1/4"],
        fx="=P(三角形包含圆心)",
        q_zh="在一个圆的圆周上随机取 3 个点，连成三角形。这个三角形包含圆心的概率是多少？",
        q_en="Pick three random points on a circle. What's the probability that the triangle they form contains the center?",
        hint="反过来想：什么时候三角形不包含圆心？",
        answer="1/4",
        value=0.25,
        steps=[
            "三角形不包含圆心 ⇔ 三个点都在同一个半圆里。",
            "以某个点为起点，另外两个点都落在它顺时针方向半圆里的概率是 (1/2)² = 1/4。",
            "三个点各当一次起点，这 3 种情况不会同时发生，所以「都在一个半圆」的概率 = 3 × 1/4 = 3/4。",
            "包含圆心的概率 = 1 − 3/4 = 1/4。",
        ],
        say_en="The triangle misses the center exactly when all three points lie in a semicircle. For each point, the chance "
               "that the other two lie in the semicircle clockwise from it is 1/4, and these events are disjoint, "
               "so that probability is 3/4. The answer is 1 − 3/4 = 1/4.",
        trap="凭对称性猜 1/2。",
        followup="圆上随机 4 个点组成的四边形包含圆心的概率？→ 1/2（n 个点都在同一个半圆的概率是 n/2ⁿ⁻¹）。",
        snippet=_code("""
            rng = np.random.default_rng(0)
            # 3 个点在圆周上的位置（一圈记为 1）
            a = np.sort(rng.random((1_000_000, 3)), axis=1)
            # 三段弧长
            gaps = np.diff(a, axis=1, append=a[:, :1] + 1)
            # 三段弧都小于半圈 ⇔ 包含圆心
            result = (gaps < 0.5).all(axis=1).mean()
        """),
        checks=[("包含圆心的概率", 0.25, "result", 0.003)],
    ),
    dict(
        id="G4", topic="连续分布 · 几何概率", level=2,
        title="木棍随机切两刀，能拼成三角形吗？",
        hook=["木棍随机切两刀", "三段能拼成", "三角形的概率？"],
        fx="=P(三段能拼成三角形)",
        q_zh="一根长度为 1 的木棍，随机选两个点切开，得到三段。这三段能拼成三角形的概率是多少？",
        q_en="Break a stick of length 1 at two uniformly random points. "
             "What's the probability that the three pieces can form a triangle?",
        hint="能拼成三角形 ⇔ 每一段都短于 1/2。画一个正方形看面积。",
        answer="1/4",
        value=0.25,
        steps=[
            "三角形条件：任意两边之和大于第三边 ⇔ 每一段都 < 1/2。",
            "两个切点 (x, y) 均匀落在单位正方形里。",
            "满足条件的区域是两个小三角形，每个面积 1/8，加起来 1/4。",
        ],
        say_en="The pieces form a triangle if and only if each is shorter than 1/2. With the cut points uniform on the "
               "unit square, that region is two triangles of area 1/8 each, so the probability is 1/4.",
        trap="答 1/2：没想清楚「每一段都要短于一半」这个条件。",
        followup="先随机切一刀，再把较长的那段随机切一刀呢？→ 2 ln 2 − 1 ≈ 0.386。",
        snippet=_code("""
            rng = np.random.default_rng(0)
            n = 1_000_000
            x = np.sort(rng.random((n, 2)), axis=1)
            a, b = x[:, 0], x[:, 1]
            pieces = np.stack([a, b - a, 1 - b], axis=1)
            result = (pieces < 0.5).all(axis=1).mean()
            c = rng.random(n)  # 追问：先切一刀
            L, S = np.maximum(c, 1 - c), np.minimum(c, 1 - c)
            d = rng.random(n) * L  # 再切较长那段
            p2 = ((S < .5) & (d < .5) & (L - d < .5)).mean()
        """),
        checks=[
            ("能拼成三角形的概率", 0.25, "result", 0.003),
            ("追问：切较长的那段", 2 * math.log(2) - 1, "p2", 0.003),
        ],
    ),
    dict(
        id="G5", topic="连续分布 · 几何概率", level=1,
        title="一小时内随机到，等15分钟能见面吗？",
        hook=["约好一小时内见面", "每人只等 15 分钟", "能见到的概率？"],
        fx="=P(|x − y| ≤ 15)",
        q_zh="两个人约好中午 12 点到 1 点之间见面，各自在这一小时里随机到达，先到的人最多等 15 分钟就走。他们能见到面的概率是多少？",
        q_en="Two people agree to meet between 12:00 and 1:00. Each arrives at a uniformly random time and waits at most "
             "15 minutes. What's the probability they meet?",
        hint="画一个 60 × 60 的正方形。见面 ⇔ |x − y| ≤ 15。",
        answer="7/16 = 43.75%",
        value=7 / 16,
        steps=[
            "两人到达时间 (x, y) 均匀落在 60 × 60 的正方形里。",
            "见不到面 ⇔ |x − y| > 15，是两个直角边为 45 的三角形，面积 = 45² = 2025。",
            "见面概率 = 1 − 2025/3600 = 1 − 9/16 = 7/16。",
        ],
        say_en="Arrival times are uniform on a 60 by 60 square, and they meet when |x − y| ≤ 15. The complement is two "
               "triangles with legs of 45, total area 2025, so the probability is 1 − 2025/3600 = 7/16.",
        trap="答 15/60 = 1/4 或 30/60 = 1/2：要画图算面积。",
        followup="想让见面概率超过一半，每人至少要等多久？→ 60 × (1 − 1/√2) ≈ 17.6 分钟。",
        snippet=_code("""
            rng = np.random.default_rng(0)
            # 到达时间（分钟）
            t = rng.random((1_000_000, 2)) * 60
            result = (np.abs(t[:, 0] - t[:, 1]) <= 15).mean()
        """),
        checks=[("见面的概率", 7 / 16, "result", 0.003)],
    ),
    dict(
        id="G6", topic="连续分布 · 正态分布", level=2,
        title="标准正态取绝对值，期望是多少？",
        hook=["标准正态", "取绝对值以后", "期望是多少？"],
        fx="=E[ABS(Z)]",
        q_zh="Z 服从标准正态分布 N(0, 1)。|Z| 的期望是多少？",
        q_en="Z is a standard normal random variable. What is E|Z|?",
        hint="写成积分 2∫₀^∞ z φ(z) dz，换元 u = z²/2。",
        answer="√(2/π) ≈ 0.798",
        value=SQRT(2 / math.pi),
        steps=[
            "E|Z| = 2∫₀^∞ z × (1/√(2π)) e^(−z²/2) dz。",
            "∫₀^∞ z e^(−z²/2) dz = 1（换元 u = z²/2）。",
            "所以 E|Z| = 2/√(2π) = √(2/π) ≈ 0.798。",
            "常用：正态分布的平均绝对偏差约等于 0.8σ。",
        ],
        say_en="E|Z| = 2∫₀^∞ z φ(z) dz, and ∫₀^∞ z e^(−z²/2) dz = 1, so E|Z| = 2/√(2π) = √(2/π) ≈ 0.80. "
               "A handy rule: the mean absolute deviation of a normal is about 0.8σ.",
        trap="答 0 或 1：0 是 E[Z]，1 是 E[Z²]。",
        followup="E[max(Z, 0)] 呢？→ 1/√(2π) ≈ 0.399。平值期权的近似定价里出现的 0.4 就是它。",
        snippet=_code("""
            rng = np.random.default_rng(0)
            z = rng.standard_normal(1_000_000)
            result = np.abs(z).mean()
            pos = np.maximum(z, 0).mean()  # 追问
        """),
        checks=[
            ("E|Z|", SQRT(2 / math.pi), "result", 0.004),
            ("追问：E[max(Z, 0)]", 1 / SQRT(2 * math.pi), "pos", 0.003),
        ],
    ),
    # ---------------- S 统计推断 ----------------
    dict(
        id="S1", topic="统计推断 · 假设检验", level=2,
        title="抛100次60次正面，硬币有问题吗？",
        hook=["抛 100 次", "60 次正面", "能说硬币不公平吗？"],
        fx="=P值(60/100, 双侧)",
        q_zh="一枚硬币抛了 100 次，出现 60 次正面。在 5% 的显著性水平下（双侧检验），能不能说这枚硬币不公平？",
        q_en="A coin lands heads 60 times in 100 flips. At the 5% level with a two-sided test, "
             "can you conclude that the coin is unfair?",
        hint="正态近似下 z 是多少？再想想：精确的二项检验会给出一样的结论吗？",
        answer="卡在边界：正态近似 p ≈ 0.046（拒绝），精确二项检验 p ≈ 0.057（不拒绝）",
        value=_P_EXACT_60,
        steps=[
            "原假设：硬币公平。正面数的均值 50，标准差 √(100 × 0.5 × 0.5) = 5。",
            "z = (60 − 50)/5 = 2.0，双侧 p ≈ 0.0455 < 0.05 → 正态近似说「拒绝」。",
            "精确二项检验：P(X ≥ 60) ≈ 0.0284，双侧 p ≈ 0.0569 > 0.05 → 「不拒绝」。",
            "加连续性校正：z = (59.5 − 50)/5 = 1.9，p ≈ 0.057，和精确检验一致。",
            "面试要说出：结果卡在边界上，正态近似偏乐观，应该用精确检验或者多收集数据。",
        ],
        say_en="Under the null the count has mean 50 and SD 5, so z = 2 and the normal approximation gives p ≈ 0.046. "
               "But the exact two-sided binomial p-value is about 0.057, and the continuity-corrected normal gives 0.057 too. "
               "It's right on the boundary, so I wouldn't call the coin unfair from this data alone.",
        trap="只会说「z = 2 > 1.96，所以拒绝」：没意识到正态近似在边界上会误判。",
        followup="想有 80% 的把握检测出正面概率 0.6 的硬币，大概要抛多少次？→ 约 194 次（5% 显著性，双侧）。",
        snippet=_code("""
            rng = np.random.default_rng(0)
            # 公平硬币抛 100 次
            x = rng.binomial(100, 0.5, 1_000_000)
            # 精确双侧 p 值
            result = (np.abs(x - 50) >= 10).mean()
        """),
        checks=[
            ("精确双侧 p 值", _P_EXACT_60, "result", 0.0015),
            ("正态近似 p 值（z = 2）", math.erfc(2 / SQRT(2)), None, 0),
        ],
    ),
    dict(
        id="S2", topic="统计推断 · 多重检验", level=1,
        title="做20次检验，至少1次显著的概率？",
        hook=["做 20 次检验", "至少 1 次「显著」", "概率是 64%"],
        fx="=P(至少一个假阳性)",
        q_zh="你做了 20 个互相独立的假设检验，每个都用 5% 的显著性水平，而且所有原假设其实都是真的。至少有一个「显著」结果的概率是多少？",
        q_en="You run 20 independent hypothesis tests at the 5% level, and every null hypothesis is actually true. "
             "What's the probability that at least one comes out significant?",
        hint="算反面：20 个都不显著。",
        answer="1 − 0.95²⁰ ≈ 64.2%",
        value=1 - 0.95 ** 20,
        steps=[
            "每个检验不出假阳性的概率是 0.95。",
            "20 个都不出：0.95²⁰ ≈ 0.358。",
            "至少一个假阳性：1 − 0.358 ≈ 64.2%。",
            "补救：Bonferroni 校正，每个检验用 0.05/20 = 0.0025 的水平。",
        ],
        say_en="Each test avoids a false positive with probability 0.95, so all 20 do with probability 0.95²⁰ ≈ 0.36. "
               "The chance of at least one false positive is about 64%. A Bonferroni correction tests each at 0.05/20.",
        trap="答 5%：每个检验是 5%，但做 20 次就远不止 5% 了。回测里反复调参能「调出」好结果，也是这个原因。",
        followup="用 Bonferroni 校正之后，至少一个假阳性的概率？→ 1 − (1 − 0.0025)²⁰ ≈ 4.9%。",
        snippet=_code("""
            rng = np.random.default_rng(0)
            # 原假设为真时 p 值 ~ U(0,1)
            p = rng.random((500_000, 20))
            result = (p < 0.05).any(axis=1).mean()
            bonf = (p < 0.05 / 20).any(axis=1).mean()
        """),
        checks=[
            ("至少一个假阳性", 1 - 0.95 ** 20, "result", 0.004),
            ("追问：Bonferroni 校正后", 1 - (1 - 0.0025) ** 20, "bonf", 0.002),
        ],
    ),
    dict(
        id="S3", topic="统计推断 · Bootstrap", level=2,
        title="有放回抽n次，多少数据从没被抽到？",
        hook=["Bootstrap 抽样", "36.8% 的数据", "一次都没被抽到"],
        fx="=P(从没被抽到)",
        q_zh="从 n 个数据点里有放回地抽 n 次（Bootstrap）。某一个数据点一次都没被抽到的概率是多少？n 很大时趋近于多少？",
        q_en="A bootstrap sample draws n times with replacement from n data points. What's the probability that a given "
             "point is never drawn? What does it approach for large n?",
        hint="每次抽不到它的概率是 1 − 1/n。",
        answer="(1 − 1/n)ⁿ，n 很大时趋近 1/e ≈ 36.8%",
        value=0.99 ** 100,
        steps=[
            "每次抽不到它：1 − 1/n。抽 n 次都抽不到：(1 − 1/n)ⁿ。",
            "n → ∞ 时趋近 1/e ≈ 0.368。n = 100 时约 0.366。",
            "所以一个 Bootstrap 样本里只有约 63.2% 的数据点出现过。",
            "随机森林的袋外样本（OOB）就是剩下的这约 36.8%。",
        ],
        say_en="Each draw misses the point with probability 1 − 1/n, so all n draws miss it with probability (1 − 1/n)ⁿ, "
               "which tends to 1/e ≈ 0.368. That's why a bootstrap sample contains about 63.2% of the distinct points, "
               "and why random forests have roughly 37% out-of-bag data.",
        trap="答 0：觉得抽了 n 次总能抽到。",
        followup="一个 Bootstrap 样本里平均有多少个不同的点？→ n × [1 − (1 − 1/n)ⁿ] ≈ 0.632n。",
        snippet=_code("""
            rng = np.random.default_rng(0)
            n, B = 100, 50_000
            # B 次有放回抽样
            idx = rng.integers(0, n, (B, n))
            hit = np.zeros((B, n), dtype=bool)
            hit[np.arange(B)[:, None], idx] = True
            result = 1 - hit.mean()  # 没被抽到的比例
        """),
        checks=[
            ("n = 100 时没被抽到的概率", 0.99 ** 100, "result", 0.002),
            ("n → ∞ 的极限 1/e", 1 / math.e, None, 0),
        ],
    ),
    dict(
        id="S4", topic="统计推断 · 线性回归", level=2,
        title="y对x斜率0.5，x对y斜率是2吗？",
        hook=["y 对 x 回归斜率 0.5", "x 对 y 回归斜率", "是 2 吗？"],
        fx="=b₁ × b₂",
        q_zh="用 y 对 x 做简单线性回归，斜率是 b₁；反过来用 x 对 y 回归，斜率是 b₂。b₁ × b₂ 等于什么？如果 b₁ = 0.5，b₂ 可以是 2 吗？",
        q_en="Regress y on x and get slope b₁; regress x on y and get slope b₂. What is b₁ × b₂? "
             "If b₁ = 0.5, can b₂ be 2?",
        hint="把两个斜率都写成协方差和方差的形式。",
        answer="b₁ × b₂ = r²。b₂ ≤ 2，等于 2 只在所有点都在一条直线上时发生",
        value=0.36,
        steps=[
            "b₁ = Cov(x, y)/Var(x)，b₂ = Cov(x, y)/Var(y)。",
            "b₁ × b₂ = Cov²/(Var(x) Var(y)) = r²。",
            "r² ≤ 1，所以 b₂ ≤ 1/b₁ = 2，等于 2 只在所有点完全共线时发生。",
            "两条回归线不是互为反函数（除非 |r| = 1），这就是「向均值回归」。",
        ],
        say_en="b₁ = Cov/Var(x) and b₂ = Cov/Var(y), so b₁b₂ = Cov²/(Var(x)Var(y)) = r². Since r² ≤ 1, b₂ ≤ 1/b₁ = 2, "
               "with equality only when the points are perfectly collinear. The two regression lines aren't inverses; "
               "that's regression to the mean.",
        trap="以为 b₂ = 1/b₁ = 2：把回归线当成了可以直接反解的方程。",
        followup="如果 x 和 y 都先标准化，两个斜率分别是多少？→ 都等于 r。",
        snippet=_code("""
            rng = np.random.default_rng(0)
            x = rng.standard_normal(200_000)
            e = rng.standard_normal(200_000)
            y = 0.6 * x + 0.8 * e  # 总体相关系数 ρ = 0.6
            b1 = np.polyfit(x, y, 1)[0]  # y 对 x 的斜率
            b2 = np.polyfit(y, x, 1)[0]  # x 对 y 的斜率
            r = np.corrcoef(x, y)[0, 1]
            result = b1 * b2
        """),
        checks=[
            ("b₁ × b₂（总体 ρ² = 0.36）", 0.36, "result", 0.006),
            ("同一份数据：b₁ × b₂ − r²", 0.0, "result - r ** 2", 1e-9),
        ],
    ),
    dict(
        id="S5", topic="统计推断 · 相关系数矩阵", level=3,
        title="三个变量两两负相关，最低能到多少？",
        hook=["三个变量", "两两负相关", "最低能到多少？"],
        fx="=MIN(ρ)",
        q_zh="X、Y、Z 三个随机变量，两两之间的相关系数都等于 ρ。ρ 最小可以是多少？",
        q_en="Three random variables X, Y and Z have the same pairwise correlation ρ. What's the smallest possible ρ?",
        hint="相关系数矩阵必须半正定。或者更快：Var(X + Y + Z) ≥ 0。",
        answer="−1/2",
        value=-0.5,
        steps=[
            "把三个变量都标准化（方差为 1）。",
            "Var(X + Y + Z) = 3 + 6ρ ≥ 0 → ρ ≥ −1/2。",
            "能取到：让 X + Y + Z = 0，三个变量互相「抵消」。",
            "一般地，n 个变量等相关时 ρ ≥ −1/(n − 1)。",
        ],
        say_en="Standardize them. Var(X + Y + Z) = 3 + 6ρ must be non-negative, so ρ ≥ −1/2, attained when X + Y + Z = 0. "
               "In general, n equicorrelated variables need ρ ≥ −1/(n − 1).",
        trap="答 −1：两个变量可以完全负相关，三个变量不可能两两都完全负相关。",
        followup="已知 Corr(X, Y) = 0.9、Corr(Y, Z) = 0.9，Corr(X, Z) 最小是多少？→ 0.62（= 0.81 − 0.19）。",
        snippet=_code("""
            rng = np.random.default_rng(0)
            w = rng.standard_normal((1_000_000, 3))
            # X+Y+Z=0
            xyz = w - w.mean(axis=1, keepdims=True)
            c = np.corrcoef(xyz.T)
            result = c[np.triu_indices(3, 1)].mean()  # 两两
            m = np.full((3, 3), -0.51) + 1.51 * np.eye(3)
            lam = np.linalg.eigvalsh(m).min()  # ρ = −0.51
        """),
        checks=[
            ("X + Y + Z = 0 时的相关系数", -0.5, "result", 0.003),
            ("ρ = −0.51：最小特征值 < 0", -0.02, "lam", 1e-9),
        ],
    ),
    dict(
        id="S6", topic="统计推断 · 组合风险", level=2, finance=True,
        title="两个资产各买一半，组合波动是多少？",
        hook=["波动 20% 和 30%", "各买一半", "组合波动不是 25%"],
        fx="=组合波动率(50/50)",
        q_zh="资产 A 年化波动率 20%，资产 B 年化波动率 30%，两者相关系数 0.5。各投一半，组合的年化波动率是多少？",
        q_en="Asset A has 20% annual volatility and asset B has 30%, with correlation 0.5. "
             "What's the volatility of a 50/50 portfolio?",
        hint="Var = w₁²σ₁² + w₂²σ₂² + 2w₁w₂ρσ₁σ₂。",
        answer="≈ 21.8%",
        value=SQRT(0.25 * 0.04 + 0.25 * 0.09 + 2 * 0.25 * 0.5 * 0.2 * 0.3),
        steps=[
            "协方差 = ρσ₁σ₂ = 0.5 × 0.2 × 0.3 = 0.03。",
            "Var = 0.25 × 0.04 + 0.25 × 0.09 + 2 × 0.25 × 0.03 = 0.01 + 0.0225 + 0.015 = 0.0475。",
            "波动率 = √0.0475 ≈ 21.8%。",
            "不是 (20% + 30%)/2 = 25%：只要相关系数 < 1，就有分散效果。",
        ],
        say_en="The covariance is 0.5 × 0.2 × 0.3 = 0.03, so the variance is 0.25 × 0.04 + 0.25 × 0.09 + 2 × 0.25 × 0.03 "
               "= 0.0475 and the volatility is about 21.8%, below the 25% average because the correlation is less than one.",
        trap="答 25%：直接把波动率平均，只有相关系数 = 1 时才对。",
        followup="波动最小的组合里 A 占多少？→ (0.09 − 0.03)/(0.04 + 0.09 − 0.06) = 6/7 ≈ 85.7%，波动率约 19.6%。",
        snippet=_code("""
            rng = np.random.default_rng(0)
            # 20%、30%、ρ = 0.5
            cov = [[0.04, 0.03], [0.03, 0.09]]
            r = rng.multivariate_normal([0, 0], cov, 1_000_000)
            result = (0.5 * r[:, 0] + 0.5 * r[:, 1]).std()
            # 追问：a = Var(A)，b = Var(B)，c = Cov(A, B)
            a, b, c = np.cov(r.T)[[0, 1, 0], [0, 1, 1]]
            w = (b - c) / (a + b - 2 * c)  # 最小方差权重
        """),
        checks=[
            ("50/50 组合的波动率", SQRT(0.0475), "result", 0.001),
            ("追问：最小方差组合里 A 的权重", 6 / 7, "w", 0.005),
        ],
    ),
]

BY_ID = {q["id"]: q for q in QUESTIONS}

# 小红书发布顺序：开头放最反直觉、受众最广的，难题和简单题穿插
ORDER = [
    "P1", "M1", "P3", "S2", "P6", "M4", "S6", "G1", "E1", "M2",
    "S1", "E3", "G3", "M6", "P2", "E4", "M3", "G4", "S3", "P4",
    "E6", "G5", "M5", "S4", "P5", "E2", "G2", "S5", "E5", "G6",
]


def run_snippet(q: dict) -> dict:
    """运行一道题的模拟代码，返回它的变量（里面有 result）。"""
    import numpy as np

    ns: dict = {"np": np}
    exec(q["snippet"], ns)
    return ns


def check_rows(q: dict, ns: dict | None = None) -> list[tuple[str, float, float | None, float]]:
    """[(项目, 公式值, 模拟值 或 None, 允许误差)]"""
    import numpy as np

    ns = run_snippet(q) if ns is None else ns
    rows = []
    for label, exact, expr, tol in q["checks"]:
        sim = None if expr is None else float(eval(expr, {"np": np}, ns))
        rows.append((label, float(exact), sim, tol))
    return rows

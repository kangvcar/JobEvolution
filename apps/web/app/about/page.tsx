import type { Metadata } from "next";
import { About } from "./about";

export const metadata: Metadata = {
  title: "关于智演 | 理念、方法、效果与边界",
  description:
    "智演为什么做、怎么做、做到了什么、不做什么。多源招聘数据驱动的岗位能力图谱：每条要求边有证据，不合成分数，人是最后一道闸。",
};

export default function AboutPage() {
  return <About />;
}

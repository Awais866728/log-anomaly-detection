"""Log message extraction and Drain3 template mining."""

import re
from pathlib import Path

import pandas as pd
from drain3 import TemplateMiner
from drain3.masking import MaskingInstruction
from drain3.template_miner_config import TemplateMinerConfig

# The "content" group is the log message.
LOG_FORMATS = {
    # 081109 203615 148 INFO dfs.DataNode$PacketResponder: <content>
    "HDFS": re.compile(r"^\d+\s+\d+\s+\d+\s+\S+\s+\S+:\s+(?P<content>.*)$"),
    # - 1117838570 2005.06.03 R02-M1-N0-C:J12-U11 2005-06-03-15.42.50.675872 R02-M1-N0-C:J12-U11 RAS KERNEL INFO <content>
    "BGL": re.compile(r"^(?:\S+\s+){9}(?P<content>.*)$"),
    # Dec 10 06:55:46 LabSZ sshd[24200]: <content>
    "OpenSSH": re.compile(r"^\S+\s+\d+\s+\S+\s+\S+\s+sshd\[\d+\]:\s+(?P<content>.*)$"),
    # [Sun Dec 04 04:47:44 2005] [notice] <content>
    "Apache": re.compile(r"^\[[^\]]*\]\s+\[[^\]]*\]\s+(?P<content>.*)$"),
}

# Order matters: specific patterns run before the generic number mask.
MASKING_INSTRUCTIONS = [
    MaskingInstruction(r"blk_-?\d+", "BLK"),
    MaskingInstruction(r"((?<=[^A-Za-z0-9])|^)(\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3})(:\d+)?((?=[^A-Za-z0-9])|$)", "IP"),
    MaskingInstruction(r"((?<=[^A-Za-z0-9])|^)(0x[a-fA-F0-9]+)((?=[^A-Za-z0-9])|$)", "HEX"),
    MaskingInstruction(r"((?<=[^A-Za-z0-9])|^)([\-\+]?\d+)((?=[^A-Za-z0-9])|$)", "NUM"),
]

# Dataset-specific masks, applied before the shared ones.
DATASET_MASKING = {
    "OpenSSH": [
        # only the word right after "invalid user" / "for user"
        MaskingInstruction(r"(?:(?<=\b[Ii]nvalid user )|(?<=\bfor user ))[^\s=]+", "USER"),
        # "... ruser= rhost=1.2.3.4 user=root"
        MaskingInstruction(r"(?<=\buser=)\S+", "USER"),
        # "Failed password for root", but not "for invalid user ..."
        MaskingInstruction(r"(?<=\bfor )(?!(?:invalid|user)\b)[^\s\[]+", "USER"),
        MaskingInstruction(r"(?<=\bport )\d+", "PORT"),
        # needs a digit so words like "added" aren't masked
        MaskingInstruction(r"(?<=\b[Ss]ession )(?=[0-9a-fA-F]*\d)[0-9a-fA-F]+\b", "SESSION"),
    ],
    "BGL": [
        # register numbers in dumps: "fpr12=" / "r07=" -> "fpr<NUM>=" / "r<NUM>="
        MaskingInstruction(r"(?:(?<=\bfpr)|(?<=\br))\d+(?==)", "NUM"),
        # hex words without 0x, e.g. "c07a533b" or "000017e7": 4+ hex characters with at least one
        # digit (so "added" or "face" stay) and one letter (plain numbers are left to the NUM mask)
        MaskingInstruction(
            r"((?<=[^A-Za-z0-9])|^)(?=[0-9a-fA-F]*\d)(?=[0-9a-fA-F]*[a-fA-F])[0-9a-fA-F]{4,}((?=[^A-Za-z0-9])|$)",
            "HEX",
        ),
    ],
}

DEFAULT_SIM_TH = 0.4
# OpenSSH templates often differ by one word, which Drain merges at 0.4.
DATASET_SIM_TH = {"OpenSSH": 0.7}


def extract_content(line, dataset):
    """Return the message part of a log line, or None if it doesn't match."""
    match = LOG_FORMATS[dataset].match(line.rstrip("\r\n"))
    return match.group("content").strip() if match else None


def masking_for(dataset=None, use_dataset_masks=True):
    extra = DATASET_MASKING.get(dataset, []) if use_dataset_masks else []
    return extra + MASKING_INSTRUCTIONS


def build_template_miner(dataset=None, sim_th=None, depth=4, use_dataset_masks=True):
    """Build a Drain3 miner; sim_th=None uses the dataset's default."""
    config = TemplateMinerConfig()
    config.drain_sim_th = sim_th if sim_th is not None else DATASET_SIM_TH.get(dataset, DEFAULT_SIM_TH)
    config.drain_depth = depth
    config.masking_instructions = masking_for(dataset, use_dataset_masks)
    return TemplateMiner(config=config)


class DrainParser:
    """Incremental Drain3 parser."""

    def __init__(self, dataset=None, sim_th=None, depth=4, use_dataset_masks=True):
        self.miner = build_template_miner(dataset, sim_th, depth, use_dataset_masks)

    def parse(self, message):
        """Return (cluster_id, current template) for a message."""
        result = self.miner.add_log_message(message)
        return result["cluster_id"], result["template_mined"]

    def template(self, cluster_id):
        return self.miner.drain.id_to_cluster[cluster_id].get_template()

    @property
    def num_templates(self):
        return len(self.miner.drain.clusters)


def parse_log_file(path, dataset, sim_th=None, depth=4, use_dataset_masks=True):
    """Parse a raw log file into a DataFrame with one row per line."""
    parser = DrainParser(dataset, sim_th, depth, use_dataset_masks)
    rows = []
    with open(Path(path), encoding="utf-8", errors="replace") as f:
        for line_id, line in enumerate(f, start=1):
            if not line.strip():
                continue
            content = extract_content(line, dataset)
            cluster_id = parser.parse(content)[0] if content is not None else None
            rows.append({"LineId": line_id, "Raw": line.rstrip("\r\n"), "Content": content, "ClusterId": cluster_id})

    df = pd.DataFrame(rows)
    # use final templates, since Drain generalises them as lines are added
    df["Template"] = df["ClusterId"].map(lambda cid: parser.template(cid) if pd.notna(cid) else None)
    return df


def grouping_accuracy(true_ids, pred_ids):
    """Loghub grouping accuracy: share of lines whose predicted group matches their true group exactly."""
    df = pd.DataFrame({"true": list(true_ids), "pred": list(pred_ids)})
    true_sizes = df["true"].value_counts()
    correct = 0
    for _, group in df.groupby("pred"):
        true_in_group = group["true"].unique()
        if len(true_in_group) == 1 and true_sizes[true_in_group[0]] == len(group):
            correct += len(group)
    return correct / len(df)

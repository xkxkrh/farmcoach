"""Fragmented MP4 (Chrome MediaRecorder) -> standard 'faststart' MP4 with a full sample index.
Single video track only. Usage: py remux.py in.mp4 out.mp4"""
import struct, sys


def boxes(b, off, end):
    i = off
    while i < end:
        sz, typ = struct.unpack(">I4s", b[i:i + 8]); hdr = 8
        if sz == 1: sz = struct.unpack(">Q", b[i + 8:i + 16])[0]; hdr = 16
        elif sz == 0: sz = end - i
        yield i, sz, hdr, typ.decode("latin1")
        i += sz


def child(b, parent, name):
    i, sz, hdr = parent
    for j, s2, h2, t in boxes(b, i + hdr, i + sz):
        if t == name: return (j, s2, h2)
    return None


def path(b, names, root=None):
    cur = root
    for n in names:
        if cur is None:
            cur = next(((i, s, h) for i, s, h, t in boxes(b, 0, len(b)) if t == n), None)
        else:
            cur = child(b, cur, n)
        if cur is None: return None
    return cur


def box(typ, payload): return struct.pack(">I4s", 8 + len(payload), typ.encode()) + payload
def full(typ, ver, flags, payload): return box(typ, struct.pack(">I", (ver << 24) | flags) + payload)


def remux(src, dst):
    b = open(src, "rb").read()
    trex = path(b, ["moov", "mvex", "trex"])
    d_dur, d_size, d_flags = struct.unpack(">III", b[trex[0] + 20:trex[0] + 32])
    samples = []  # (data_offset, size, duration, flags, cto)
    for i, sz, hdr, t in boxes(b, 0, len(b)):
        if t != "moof": continue
        moof = (i, sz, hdr); traf = child(b, moof, "traf")
        tfhd = child(b, traf, "tfhd"); fl = int.from_bytes(b[tfhd[0] + 9:tfhd[0] + 12], "big")
        p = tfhd[0] + 16; base = i  # default-base-is-moof
        dd, ds, df = d_dur, d_size, d_flags
        if fl & 0x1: base = struct.unpack(">Q", b[p:p + 8])[0]; p += 8
        if fl & 0x2: p += 4
        if fl & 0x8: dd = struct.unpack(">I", b[p:p + 4])[0]; p += 4
        if fl & 0x10: ds = struct.unpack(">I", b[p:p + 4])[0]; p += 4
        if fl & 0x20: df = struct.unpack(">I", b[p:p + 4])[0]; p += 4
        for j, s2, h2, t2 in boxes(b, traf[0] + traf[2], traf[0] + traf[1]):
            if t2 != "trun": continue
            tf = int.from_bytes(b[j + 9:j + 12], "big"); ver = b[j + 8]
            n = struct.unpack(">I", b[j + 12:j + 16])[0]; q = j + 16
            off = base
            if tf & 0x1: off = base + struct.unpack(">i", b[q:q + 4])[0]; q += 4
            first = None
            if tf & 0x4: first = struct.unpack(">I", b[q:q + 4])[0]; q += 4
            for k in range(n):
                dur = dd; size = ds; flg = df; cto = 0
                if tf & 0x100: dur = struct.unpack(">I", b[q:q + 4])[0]; q += 4
                if tf & 0x200: size = struct.unpack(">I", b[q:q + 4])[0]; q += 4
                if tf & 0x400: flg = struct.unpack(">I", b[q:q + 4])[0]; q += 4
                if tf & 0x800: cto = struct.unpack(">i" if ver else ">I", b[q:q + 4])[0]; q += 4
                if k == 0 and first is not None: flg = first
                samples.append((off, size, dur, flg, cto)); off += size
    # media info from original moov
    mdhd = path(b, ["moov", "trak", "mdia", "mdhd"]); mv = b[mdhd[0] + 8]
    ts = struct.unpack(">I", b[mdhd[0] + (28 if mv else 20):mdhd[0] + (32 if mv else 24)])[0]
    stsd = path(b, ["moov", "trak", "mdia", "minf", "stbl", "stsd"])
    stsd_raw = b[stsd[0]:stsd[0] + stsd[1]]
    tkhd = path(b, ["moov", "trak", "tkhd"]); tv = b[tkhd[0] + 8]
    wh = b[tkhd[0] + tkhd[1] - 8:tkhd[0] + tkhd[1]]  # width/height 16.16
    hdlr = path(b, ["moov", "trak", "mdia", "hdlr"]); hdlr_raw = b[hdlr[0]:hdlr[0] + hdlr[1]]
    vmhd = path(b, ["moov", "trak", "mdia", "minf", "vmhd"]); vmhd_raw = b[vmhd[0]:vmhd[0] + vmhd[1]]
    dinf = path(b, ["moov", "trak", "mdia", "minf", "dinf"]); dinf_raw = b[dinf[0]:dinf[0] + dinf[1]]
    total = sum(s[2] for s in samples)
    movie_ts = 1000; movie_dur = round(total * movie_ts / ts)
    # stts (run-length)
    runs = []
    for s in samples:
        if runs and runs[-1][1] == s[2]: runs[-1][0] += 1
        else: runs.append([1, s[2]])
    stts = full("stts", 0, 0, struct.pack(">I", len(runs)) + b"".join(struct.pack(">II", c, d) for c, d in runs))
    ctts = b""
    if any(s[4] for s in samples):
        cr = []
        for s in samples:
            if cr and cr[-1][1] == s[4]: cr[-1][0] += 1
            else: cr.append([1, s[4]])
        ctts = full("ctts", 0, 0, struct.pack(">I", len(cr)) + b"".join(struct.pack(">II", c, d) for c, d in cr))
    keys = [i + 1 for i, s in enumerate(samples) if not (s[3] & 0x00010000)]
    stss = full("stss", 0, 0, struct.pack(">I", len(keys)) + b"".join(struct.pack(">I", k) for k in keys))
    stsz = full("stsz", 0, 0, struct.pack(">II", 0, len(samples)) + b"".join(struct.pack(">I", s[1]) for s in samples))
    stsc = full("stsc", 0, 0, struct.pack(">I", 1) + struct.pack(">III", 1, 1, 1))  # one sample per chunk

    def build(chunk_base):
        offs, o = [], chunk_base
        for s in samples: offs.append(o); o += s[1]
        co = full("co64", 0, 0, struct.pack(">I", len(offs)) + b"".join(struct.pack(">Q", x) for x in offs))
        stbl = box("stbl", stsd_raw + stts + ctts + stss + stsz + stsc + co)
        minf = box("minf", vmhd_raw + dinf_raw + stbl)
        mdhd_n = full("mdhd", 0, 0, struct.pack(">IIII", 0, 0, ts, total) + struct.pack(">HH", 0x55C4, 0))
        mdia = box("mdia", mdhd_n + hdlr_raw + minf)
        matrix = struct.pack(">9I", 0x10000, 0, 0, 0, 0x10000, 0, 0, 0, 0x40000000)
        tkhd_n = full("tkhd", 0, 3, struct.pack(">IIIII", 0, 0, 1, 0, movie_dur) + b"\0" * 8 + struct.pack(">hhhH", 0, 0, 0, 0) + matrix + wh)
        trak = box("trak", tkhd_n + mdia)
        mvhd = full("mvhd", 0, 0, struct.pack(">IIII", 0, 0, movie_ts, movie_dur) + struct.pack(">IH", 0x10000, 0x100) + b"\0" * 10 + matrix + b"\0" * 24 + struct.pack(">I", 2))
        return box("moov", mvhd + trak)

    ftyp = box("ftyp", b"isom" + struct.pack(">I", 0x200) + b"isomiso2avc1mp41")
    moov = build(0)
    data_len = sum(s[1] for s in samples)
    mdat_hdr = struct.pack(">I4sQ", 1, b"mdat", 16 + data_len)
    moov = build(len(ftyp) + len(moov) + len(mdat_hdr))
    with open(dst, "wb") as f:
        f.write(ftyp); f.write(moov); f.write(mdat_hdr)
        for s in samples: f.write(b[s[0]:s[0] + s[1]])
    return len(samples), len(keys), movie_dur / movie_ts


if __name__ == "__main__":
    print("samples, keyframes, seconds:", remux(sys.argv[1], sys.argv[2]))

import os,tempfile,unittest,time
os.environ['DATA_DIR']=tempfile.mkdtemp(prefix='gas-test-')
from app.main import db,ingest,put

class ReplayTests(unittest.TestCase):
    def setUp(self):
        with db:
            db.execute('DELETE FROM events');put('pulse_volume',.01);put('configured',True)
    def event(self,seq,pulses=2,total=None):
        return {'seq':seq,'minute':int(time.time()/60)-60+seq,'pulses':pulses,'total':total if total is not None else seq*2,'flags':0}
    def test_replay_duplicate_is_not_consumed_twice(self):
        e=self.event(1)
        self.assertEqual(ingest('gas-meter-test',e),1)
        ingest('gas-meter-test',e)
        self.assertEqual(db.execute('SELECT SUM(pulses*volume) FROM events').fetchone()[0],.02)
    def test_collision_is_never_acknowledged(self):
        ingest('gas-meter-test',self.event(1))
        with self.assertRaises(ValueError):ingest('gas-meter-test',self.event(1,3,3))
    def test_offline_backlog_retains_original_times(self):
        for seq in range(1,61):ingest('gas-meter-test',self.event(seq))
        self.assertEqual(db.execute('SELECT COUNT(*) FROM events').fetchone()[0],60)
        self.assertAlmostEqual(db.execute('SELECT SUM(pulses*volume) FROM events').fetchone()[0],1.2)
    def test_clock_unknown_is_preserved(self):
        e=self.event(1);e['minute']=0;e['flags']=1
        ingest('gas-meter-test',e)
        self.assertEqual(db.execute('SELECT minute FROM events').fetchone()[0],0)
    def test_counter_reversal_rejected(self):
        ingest('gas-meter-test',self.event(1,total=100))
        with self.assertRaises(ValueError):ingest('gas-meter-test',self.event(2,total=3))
    def test_calibration_does_not_rewrite_consumption(self):
        ingest('gas-meter-test',self.event(1))
        with db:put('offset',4000)
        self.assertEqual(db.execute('SELECT pulses*volume FROM events').fetchone()[0],.02)
if __name__=='__main__':unittest.main()

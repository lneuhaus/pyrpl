from pyrpl.gui import RedPitayaGui


r = RedPitayaGui(hostname="10.214.1.28")

r.asg1.output_direct = 'out2'
r.asg.setup(waveform="ramp",
              frequency=FREQUENCY,
              amplitude=1,
              offset=0,
              trigger_source='immediately')


r.asg1.setup(waveform="ramp",
              frequency=FREQUENCY,
              amplitude=1,
              offset=0.5,
              trigger_source='off')
r.asg1.trig()

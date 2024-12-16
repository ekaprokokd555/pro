import boto3
import time
import paramiko
from botocore.exceptions import NoCredentialsError, PartialCredentialsError

# Konfigurasi AWS
AWS_REGION = 'us-east-1'  # Ganti dengan region yang diinginkan
AMI_ID = 'ami-0ac80df6eff0e70b5'  # Ganti dengan ID AMI untuk Ubuntu
INSTANCE_TYPE = 't2.micro'  # Gunakan t2.micro untuk uji coba atau sesuai dengan kebutuhan Anda
KEY_NAME = 'your-key.pem'  # Ganti dengan path ke file key pair Anda
SECURITY_GROUP_ID = 'sg-xxxxxxxx'  # Ganti dengan ID Security Group yang mengizinkan akses SSH (port 22)
SUBNET_ID = 'subnet-xxxxxxxx'  # Ganti dengan ID subnet jika perlu

# Konfigurasi proxy Lumina
LUMINA_PROXY_HOST = 'proxy.lumina.com'  # Ganti dengan host proxy Lumina
LUMINA_PROXY_PORT = 1080  # Ganti dengan port yang diberikan oleh Lumina (contoh: 1080 untuk SOCKS5)

def create_ec2_instance():
    ec2_client = boto3.client('ec2', region_name=AWS_REGION)

    try:
        # Membuat instance EC2
        response = ec2_client.run_instances(
            ImageId=AMI_ID,
            InstanceType=INSTANCE_TYPE,
            MinCount=1,
            MaxCount=1,
            KeyName=KEY_NAME,
            SecurityGroupIds=[SECURITY_GROUP_ID],
            SubnetId=SUBNET_ID,
            TagSpecifications=[{
                'ResourceType': 'instance',
                'Tags': [{
                    'Key': 'Name',
                    'Value': 'Lumina-Proxy-Instance'
                }]
            }]
        )
        instance_id = response['Instances'][0]['InstanceId']
        print(f"Instance EC2 dengan ID {instance_id} berhasil dibuat.")
        return instance_id

    except (NoCredentialsError, PartialCredentialsError) as e:
        print("Kredensial AWS tidak valid.")
        return None
    except Exception as e:
        print(f"Gagal membuat instance EC2: {e}")
        return None

def wait_for_instance_running(instance_id):
    ec2_client = boto3.client('ec2', region_name=AWS_REGION)
    
    print("Menunggu instance untuk menjalankan...")
    while True:
        response = ec2_client.describe_instances(InstanceIds=[instance_id])
        state = response['Reservations'][0]['Instances'][0]['State']['Name']
        
        if state == 'running':
            print("Instance berhasil berjalan.")
            break
        else:
            print("Menunggu...")
            time.sleep(10)

def configure_proxy(instance_ip):
    # SSH ke EC2 Instance
    ssh_client = paramiko.SSHClient()
    ssh_client.set_missing_host_key_policy(paramiko.AutoAddPolicy())

    try:
        print(f"Menghubungkan ke instance EC2 di {instance_ip} menggunakan SSH...")
        ssh_client.connect(instance_ip, username='ubuntu', key_filename=KEY_NAME)

        # Menginstal Squid Proxy
        print("Menginstal Squid Proxy...")
        commands = [
            "sudo apt-get update",
            "sudo apt-get install squid -y"
        ]
        for command in commands:
            stdin, stdout, stderr = ssh_client.exec_command(command)
            print(stdout.read().decode())

        # Mengonfigurasi Squid Proxy
        print("Mengonfigurasi Squid Proxy...")
        squid_config = """
http_port 3128
cache_peer {lumina_proxy_host} parent {lumina_proxy_port} 0 no-query default
never_direct allow all
"""
        squid_config = squid_config.format(lumina_proxy_host=LUMINA_PROXY_HOST, lumina_proxy_port=LUMINA_PROXY_PORT)

        # Menulis konfigurasi Squid ke file
        sftp_client = ssh_client.open_sftp()
        squid_file_path = '/etc/squid/squid.conf'
        with sftp_client.open(squid_file_path, 'w') as squid_file:
            squid_file.write(squid_config)
        sftp_client.close()

        # Restart Squid
        print("Merestart Squid...")
        ssh_client.exec_command('sudo systemctl restart squid')

        print("Proxy telah dikonfigurasi dengan sukses!")

    except Exception as e:
        print(f"Gagal mengonfigurasi proxy: {e}")
    finally:
        ssh_client.close()

def get_instance_ip(instance_id):
    ec2_client = boto3.client('ec2', region_name=AWS_REGION)
    response = ec2_client.describe_instances(InstanceIds=[instance_id])
    return response['Reservations'][0]['Instances'][0]['PublicIpAddress']

if __name__ == '__main__':
    instance_id = create_ec2_instance()
    if instance_id:
        wait_for_instance_running(instance_id)
        instance_ip = get_instance_ip(instance_id)
        print(f"Instance IP: {instance_ip}")
        configure_proxy(instance_ip)
